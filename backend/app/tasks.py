"""Background tasks and helper functions for job scraping."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal, get_db, manager
from app.models import AnalysisRun, Channel, Developer, Job, Message, Operation, TelegramAccount, WebsiteSource
from telegram_processor import TelegramClientManager, fetch_messages
from services.ollama_service import get_analyzer, is_ollama_available, should_analyze_message

logger = logging.getLogger(__name__)

# Global stop events for cancelling analysis (per-channel)
analysis_stop_events: dict[int, asyncio.Event] = {}

# Website source stop events (for website fetch/analyze operations)
website_stop_events: dict[int, asyncio.Event] = {}

# Bulk operation stop events (for analyze-all, fetch-analyze-all)
bulk_stop_events: dict[str, asyncio.Event] = {}

# Cron job state
cron_running = False
cron_task: asyncio.Task | None = None
_cron_lock = asyncio.Lock()


def reset_stop_event(channel_id: int):
    """Reset stop event for a channel before starting analysis."""
    cleanup_old_stop_events()
    analysis_stop_events[channel_id] = asyncio.Event()


def stop_analysis(channel_id: int):
    """Signal analysis to stop for a specific channel."""
    if channel_id in analysis_stop_events:
        analysis_stop_events[channel_id].set()


def is_analysis_stopped(channel_id: int) -> bool:
    """Check if analysis should stop for a channel."""
    event = analysis_stop_events.get(channel_id)
    if event is None:
        return False
    return event.is_set()


def cleanup_stop_event(channel_id: int):
    """Clean up stop event after analysis completes."""
    analysis_stop_events.pop(channel_id, None)


def reset_website_stop_event(source_id: int):
    """Reset stop event for a website source before starting operation."""
    website_stop_events[source_id] = asyncio.Event()


def stop_website_operation(source_id: int):
    """Signal website operation to stop for a specific source."""
    if source_id in website_stop_events:
        website_stop_events[source_id].set()


def is_website_operation_stopped(source_id: int) -> bool:
    """Check if website operation should stop for a source."""
    event = website_stop_events.get(source_id)
    if event is None:
        return False
    return event.is_set()


def cleanup_website_stop_event(source_id: int):
    """Clean up website stop event after operation completes."""
    website_stop_events.pop(source_id, None)


def reset_bulk_stop_event(operation_id: str):
    """Reset stop event for a bulk operation."""
    import logging
    logger = logging.getLogger(__name__)
    bulk_stop_events[operation_id] = asyncio.Event()
    logger.info(f"[STOP EVENT] Bulk operation {operation_id} - Reset/stop event created")


def stop_bulk_operation(operation_id: str):
    """Signal bulk operation to stop."""
    import logging
    logger = logging.getLogger(__name__)
    if operation_id in bulk_stop_events:
        bulk_stop_events[operation_id].set()
        logger.info(f"[STOP SIGNAL] Bulk operation {operation_id} - STOP event set")
    else:
        logger.warning(f"[STOP SIGNAL] Bulk operation {operation_id} - no stop event found in memory (already finished or not started?)")


def is_bulk_operation_stopped(operation_id: str) -> bool:
    """Check if bulk operation should stop."""
    event = bulk_stop_events.get(operation_id)
    if event is None:
        return False
    is_stopped = event.is_set()
    if is_stopped:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[STOP CHECK] Bulk operation {operation_id} - STOP detected")
    return is_stopped


def cleanup_bulk_stop_event(operation_id: str):
    """Clean up bulk stop event after operation completes."""
    bulk_stop_events.pop(operation_id, None)


def cleanup_old_stop_events(max_age_seconds: int = 3600):
    """Remove already-set (finished) stop events to prevent memory leak."""
    stale = [cid for cid, e in list(analysis_stop_events.items()) if e.is_set()]
    for cid in stale:
        analysis_stop_events.pop(cid, None)
    stale_bulk = [oid for oid, e in list(bulk_stop_events.items()) if e.is_set()]
    for oid in stale_bulk:
        bulk_stop_events.pop(oid, None)


async def cleanup_stale_operations():
    """Mark stale 'running' operations as 'stopped' on backend startup.
    Stale operations are those that have been running for more than 1 hour
    or whose stop events are not in memory (indicating a crash).
    """
    async with AsyncSessionLocal() as db:
        try:
            # Find all operations with status 'running'
            result = await db.execute(
                select(Operation).filter(Operation.status == "running")
            )
            stale_ops = result.scalars().all()

            if not stale_ops:
                logger.info("[CLEANUP] No stale operations found")
                return

            stale_count = 0
            for op in stale_ops:
                # Check if operation is stale:
                # 1. Running for more than 1 hour, OR
                # 2. No corresponding stop event in memory (crash scenario)
                is_stale = False

                if op.started_at:
                    age = datetime.now(timezone.utc) - op.started_at.replace(tzinfo=timezone.utc)
                    if age > timedelta(hours=1):
                        is_stale = True
                        logger.info(f"[CLEANUP] Operation {op.id} stale: running for {age}")

                # Check if stop event exists in memory
                if op.channel_id and op.channel_id not in analysis_stop_events:
                    is_stale = True
                    logger.info(f"[CLEANUP] Operation {op.id} stale: no stop event for channel {op.channel_id}")

                if op.bulk_operation_id and op.bulk_operation_id not in bulk_stop_events:
                    is_stale = True
                    logger.info(f"[CLEANUP] Operation {op.id} stale: no stop event for bulk {op.bulk_operation_id}")

                if is_stale:
                    op.status = "stopped"
                    stale_count += 1

            if stale_count > 0:
                await db.commit()
                logger.info(f"[CLEANUP] Marked {stale_count} stale operations as stopped")
            else:
                logger.info(f"[CLEANUP] Found {len(stale_ops)} running operations, none are stale")

        except Exception as e:
            logger.error(f"[CLEANUP] Failed to cleanup stale operations: {e}")
            await db.rollback()


def is_cron_running() -> bool:
    return cron_running


async def start_cron_task() -> bool:
    global cron_running, cron_task
    async with _cron_lock:
        if cron_running:
            return False
        cron_running = True
        cron_task = asyncio.create_task(continuous_scanner())
        return True


async def stop_cron_task() -> bool:
    global cron_running, cron_task
    async with _cron_lock:
        if not cron_running:
            return False
        cron_running = False
        if cron_task:
            cron_task.cancel()
            cron_task = None
        return True


async def broadcast_progress(event_type: str, data: dict):
    try:
        message = {"type": event_type, **data}
        await manager.broadcast(message)
    except Exception:
        pass


async def create_operation(
    db: AsyncSession,
    operation_type: str,
    channel: Optional[Channel],
    total_messages: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> int:
    operation = Operation(
        operation_type=operation_type,
        channel_id=channel.id if channel else None,
        channel_username=channel.username if channel else None,
        bulk_operation_id=bulk_operation_id,
        status="running",
        total_messages=total_messages or 0,
    )
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    return operation.id


async def update_operation(
    db: AsyncSession,
    operation_id: int,
    status: Optional[str] = None,
    current: Optional[int] = None,
    total: Optional[int] = None,
    total_messages: Optional[int] = None,
    analyzed: Optional[int] = None,
    jobs_found: Optional[int] = None,
    developers_found: Optional[int] = None,
    error_message: Optional[str] = None,
    channel_username: Optional[str] = None,
    commit: bool = True,
):
    """Update operation progress. Use commit=False to batch updates."""
    result = await db.execute(select(Operation).filter(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if operation:
        old_analyzed = operation.analyzed
        if status is not None:
            operation.status = status
        if current is not None:
            operation.current = current
        if total is not None:
            operation.total = total
        if total_messages is not None:
            operation.total_messages = total_messages
        if analyzed is not None:
            operation.analyzed = analyzed
        if jobs_found is not None:
            operation.jobs_found = jobs_found
        if channel_username is not None:
            operation.channel_username = channel_username
        if developers_found is not None:
            operation.developers_found = developers_found
        if error_message is not None:
            operation.error_message = error_message
        if status in ("completed", "stopped", "error"):
            operation.completed_at = datetime.utcnow()
        if commit:
            await db.commit()
            logger.info(f"[DB UPDATE] Op:{operation_id} | analyzed:{old_analyzed}->{analyzed} | status:{status} | commit:OK")
    else:
        logger.warning(f"[DB UPDATE] Op:{operation_id} - Operation not found!")


# ── HELPERS ───────────────────────────────────────────────────────────────────


def _first_contact(value) -> Optional[str]:
    """Return the first contact value from contacts array or string."""
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                v = item.get("value")
                if v:
                    return v
            elif item:
                return str(item)
        return None
    return str(value)


def _first_contact_type(value) -> Optional[str]:
    """Return the first contact type from contacts array."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                t = item.get("type")
                if t:
                    return t
        return None
    if isinstance(value, str):
        return value
    return None


def _to_str(value) -> Optional[str]:
    """Convert list or value to comma-separated string. Handle dict objects with 'value' field."""
    if value is None:
        return None
    if isinstance(value, list):
        processed = []
        for v in value:
            if isinstance(v, dict):
                val = v.get("value")
                if val:
                    processed.append(str(val))
            elif v:
                processed.append(str(v))
        return ", ".join(processed) or None
    if isinstance(value, dict):
        val = value.get("value")
        if val:
            return str(val)
    return str(value)


def _to_bool(value) -> Optional[bool]:
    """Convert list or value to boolean. If list, return True if any element is truthy."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, list):
        return any(v if isinstance(v, bool) else bool(v) for v in value)
    return bool(value)


def _resolve_contact(contacts, message) -> tuple[Optional[str], Optional[str]]:
    """Return (contact_value, contact_type), falling back to sender info."""
    contact = _first_contact(contacts)
    contact_type = _first_contact_type(contacts)
    if not contact:
        contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
        contact_type = "telegram" if contact else None
    return contact, contact_type


# ── FETCH ─────────────────────────────────────────────────────────────────────

async def fetch_and_store_messages(
    db: AsyncSession,
    channel: Channel,
    days_back: int = 15,
    run_id: Optional[int] = None,
    account_id: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> dict:
    """Fetch messages from Telegram and store in database."""
    if account_id:
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            return {"success": False, "error": "Telegram account not found"}
    elif channel.telegram_account_id:
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == channel.telegram_account_id))
        account = result.scalar_one_or_none()
        if not account:
            return {"success": False, "error": "Associated Telegram account not found"}
    else:
        result = await db.execute(
            select(TelegramAccount).filter(
                TelegramAccount.is_active == True,
                TelegramAccount.is_authenticated == True,
            )
        )
        account = result.scalars().first()
        if not account:
            return {
                "success": False,
                "error": "No active authenticated Telegram account found. Please add and authenticate an account in settings.",
            }

    telegram_manager = TelegramClientManager(
        api_id=account.api_id,
        api_hash=account.api_hash,
        phone_number=account.phone_number,
        session_name=account.session_name,
    )

    operation_id = await create_operation(db, "fetch", channel, bulk_operation_id=bulk_operation_id)
    logger.info(f"[FETCH START] Channel: {channel.username} | Days: {days_back} | BulkOp: {bulk_operation_id or 'none'}")

    try:
        await broadcast_progress("fetch_start", {"channel": channel.username, "days_back": days_back, "operation_id": operation_id})
        await telegram_manager.connect()

        await broadcast_progress("fetch_progress", {"channel": channel.username, "status": "fetching", "operation_id": operation_id})
        messages = await fetch_messages(
            telegram_manager.client,
            channel.username,
            days_back=days_back,
        )
        await broadcast_progress("fetch_progress", {"channel": channel.username, "status": "fetched", "count": len(messages), "operation_id": operation_id})
        logger.info(f"[FETCH FETCHED] Channel: {channel.username} | Messages to store: {len(messages)}")

        # Update operation with total messages count
        await update_operation(db, operation_id, total_messages=len(messages))

        new_count = 0
        stopped_early = False
        for i, msg_data in enumerate(messages):
            # Check if bulk operation was stopped (every 10 messages)
            if bulk_operation_id and (i % 10 == 0) and is_bulk_operation_stopped(bulk_operation_id):
                await broadcast_progress("fetch_progress", {
                    "channel": channel.username,
                    "status": "stopped",
                    "processed": i,
                    "total": len(messages),
                    "operation_id": operation_id,
                })
                stopped_early = True
                break

            try:
                result = await db.execute(
                    select(Message).filter(
                        Message.telegram_id == msg_data["id"],
                        Message.channel_id == channel.id,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    continue

                sender = msg_data.get("sender") or {}
                has_text = bool(msg_data.get("text"))

                async with db.begin_nested():
                    message = Message(
                        telegram_id=msg_data["id"],
                        channel_id=channel.id,
                        date=msg_data.get("date"),
                        text=msg_data.get("text"),
                        sender_id=msg_data.get("sender_id"),
                        sender_username=sender.get("username"),
                        sender_first_name=sender.get("first_name"),
                        has_image=msg_data.get("has_image", False),
                        analysis_status="pending" if has_text else "skipped",
                    )
                    db.add(message)
                    await db.flush()
                new_count += 1

                if (i + 1) % 10 == 0:
                    await broadcast_progress("fetch_progress", {
                        "channel": channel.username,
                        "processed": i + 1,
                        "total": len(messages),
                        "total_messages": len(messages),
                        "analyzed": i + 1,  # For frontend progress bar
                        "new": new_count,
                        "operation_id": operation_id,
                    })
                    await update_operation(db, operation_id, current=i + 1, total=len(messages), analyzed=i + 1)

            except Exception as e:
                logger.warning(f"Failed to store message {msg_data.get('id')}: {e}")
                continue

        await db.commit()

        channel.last_fetch_new_count = new_count
        channel.last_fetch_at = datetime.utcnow()
        await db.commit()

        status = "stopped" if stopped_early else "completed"
        logger.info(f"[FETCH COMPLETE] Channel: {channel.username} | Status: {status} | New messages: {new_count} | Total processed: {i+1 if 'i' in locals() else 0}")
        await broadcast_progress("fetch_complete", {"channel": channel.username, "new_messages": new_count, "operation_id": operation_id, "stopped": stopped_early})
        await update_operation(db, operation_id, status=status)

        if run_id:
            try:
                result = await db.execute(select(AnalysisRun).filter(AnalysisRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.messages_fetched += len(messages)
                    await db.commit()
            except Exception as e:
                await db.rollback()

        return {
            "success": True,
            "fetched": len(messages),
            "new_stored": new_count,
        }

    except Exception as e:
        await db.rollback()
        await update_operation(db, operation_id, status="error", error_message=str(e))
        # Broadcast error to frontend so it clears the UI
        await broadcast_progress("error", {
            "channel": channel_username,
            "channel_id": channel_id,
            "operation_id": operation_id,
            "error": str(e),
        })
        logger.error(f"[FETCH ERROR] Channel: {channel_username} | Error: {e}")
        error_msg = str(e).lower()
        invalid_channel_errors = [
            "channel not found", "channel invalid", "username not occupied",
            "username invalid", "no such entity", "private", "forbidden",
        ]
        if any(err in error_msg for err in invalid_channel_errors):
            try:
                await db.delete(channel)
                await db.commit()
            except Exception:
                await db.rollback()
            return {"success": False, "error": f"Channel removed: {str(e)}", "channel_removed": True}

        return {"success": False, "error": str(e)}

    finally:
        try:
            await telegram_manager.disconnect()
        except Exception:
            pass


# ── ANALYZE ───────────────────────────────────────────────────────────────────

async def _analyze_single(analyzer, message, channel_username: str):
    """Analyze a single message, returning (message, result, error)."""
    import time
    start_time = time.time()
    msg_preview = message.text[:50] if message.text else "[no text]"
    logger.info(f"[ANALYZE MSG START] Channel: {channel_username} | Msg: {msg_preview}...")
    
    try:
        result = await asyncio.wait_for(
            analyzer.analyze_message(message.text),
            timeout=60,  # Reduced from 120 to 60 seconds
        )
        elapsed = time.time() - start_time
        logger.info(f"[ANALYZE MSG DONE] Channel: {channel_username} | Msg: {msg_preview}... | Time: {elapsed:.1f}s | Result: {result.get('category') if result else 'none'}")
        return message, result, None
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        logger.warning(f"[ANALYZE MSG TIMEOUT] Channel: {channel_username} | Msg: {msg_preview}... | Time: {elapsed:.1f}s")
        return message, None, Exception(f"Analysis timeout after 60s")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[ANALYZE MSG ERROR] Channel: {channel_username} | Msg: {msg_preview}... | Time: {elapsed:.1f}s | Error: {e}")
        return message, None, e


async def analyze_messages(
    db: AsyncSession,
    channel: Channel,
    run_id: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> dict:
    """Analyze unanalyzed messages with AI using concurrent pipeline."""
    # Capture primitives immediately — any await/commit expires the ORM object
    channel_id = channel.id
    channel_username = channel.username
    channel_name = channel.name

    if not await is_ollama_available():
        return {"success": False, "error": "Ollama not available"}

    try:
        reset_stop_event(channel_id)

        messages_result = await db.execute(
            select(Message).filter(
                Message.channel_id == channel_id,
                Message.analysis_status == "pending",
            )
        )
        messages = messages_result.scalars().all()
        total_messages = len(messages)

        operation_id = await create_operation(db, "analyze", channel, total_messages=total_messages, bulk_operation_id=bulk_operation_id)

        await broadcast_progress("analyze_start", {"channel": channel_username, "channel_id": channel_id, "operation_id": operation_id})
        await broadcast_progress("analyze_progress", {"channel": channel_username, "status": "found", "total": total_messages, "operation_id": operation_id})
        await update_operation(db, operation_id, total_messages=total_messages)

        if len(messages) == 0:
            await update_operation(db, operation_id, status="completed")
            return {"success": True, "analyzed": 0, "jobs_found": 0, "developers_found": 0, "skipped": 0}

        analyzer = get_analyzer()

        jobs_added = 0
        devs_added = 0
        skipped_count = 0
        analyzed_count = 0
        stopped_count = 0
        total_messages = len(messages)
        batch_size = 3
        total_batches = (total_messages + batch_size - 1) // batch_size

        total_input_tokens = 0
        total_output_tokens = 0
        message_results: list[dict] = []

        # Circuit breaker: stop after too many consecutive batch failures
        consecutive_failures = 0
        max_consecutive_failures = 5

        logger.info(f"[ANALYZE START] Channel: {channel_username} | Messages: {total_messages} | Batches: {total_batches} | BulkOp: {bulk_operation_id or 'none'}")

        for batch_num, batch_start in enumerate(range(0, total_messages, batch_size), 1):
            # Check both individual channel stop and bulk operation stop
            if is_analysis_stopped(channel_id):
                logger.info(f"[ANALYZE STOP] Channel: {channel_username} - Individual stop signal received")
                stopped_count = total_messages - batch_start
                break
            if bulk_operation_id and is_bulk_operation_stopped(bulk_operation_id):
                logger.info(f"[ANALYZE STOP] Channel: {channel_username} - Bulk stop signal received for {bulk_operation_id}")
                stopped_count = total_messages - batch_start
                break

            # Circuit breaker: stop if too many consecutive failures
            if consecutive_failures >= max_consecutive_failures:
                logger.error(f"[ANALYZE CIRCUIT BREAKER] Channel: {channel_username} - Stopping after {consecutive_failures} consecutive batch failures")
                stopped_count = total_messages - batch_start
                break

            logger.info(f"[ANALYZE BATCH] Channel: {channel_username} | Batch {batch_num}/{total_batches} | Messages {batch_start}-{min(batch_start+batch_size, total_messages)}")

            batch = messages[batch_start:batch_start + batch_size]

            # Pre-filter: skip spam and empty messages
            filtered_messages = []
            for msg in batch:
                if msg.text and should_analyze_message(msg.text):
                    filtered_messages.append(msg)
                else:
                    skipped_count += 1
                    msg.analysis_status = "skipped"

            if not filtered_messages:
                await broadcast_progress("analyze_progress", {"channel": channel_username, "current": batch_num, "total": total_batches, "operation_id": operation_id})
                await update_operation(db, operation_id, current=batch_num)
                continue

            tasks = [_analyze_single(analyzer, msg, channel_username) for msg in filtered_messages]
            completed = await asyncio.gather(*tasks)

            for message, result, error in completed:
                msg_status = "success"

                if error:
                    skipped_count += 1
                    message.analysis_status = "skipped"
                    msg_status = "failed"
                    message_results.append({
                        "message_id": message.id,
                        "status": msg_status,
                        "error": str(error),
                    })
                    continue

                if not result or result.get("category") == "other":
                    skipped_count += 1
                    message.analysis_status = "skipped"
                    msg_status = "other"
                    message_results.append({
                        "message_id": message.id,
                        "status": msg_status,
                    })
                    continue

                # Track token usage
                usage = result.get("usage", {})
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)

                category = _to_str(result.get("category"))
                confidence = _to_str(result.get("confidence"))
                translated_text = _to_str(result.get("translated_text"))

                if not confidence or not category:
                    msg_status = "json_cutoff"
                else:
                    msg_status = "success"

                message_results.append({
                    "message_id": message.id,
                    "status": msg_status,
                    "category": category,
                    "confidence": confidence,
                })

                # ── JOB POSTING ───────────────────────────────────────────────
                if category == "job_posting":
                    job_data = result.get("job_posting") or {}

                    is_remote = _to_bool(job_data.get("is_remote"))
                    if is_remote is False:
                        # On-site only — not relevant for this board
                        skipped_count += 1
                        message.analysis_status = "skipped"
                        continue

                    # title is no longer a separate LLM field — extract from summary first sentence
                    summary_text = _to_str(job_data.get("summary"))
                    title = _to_str(job_data.get("title"))  # fallback if model still returns it
                    if not title and summary_text:
                        title = summary_text.split(".")[0].strip()[:200]
                    if not title:
                        title = f"[No Title] sender:{message.sender_username or message.sender_id or 'unknown'}"
                    company = _to_str(job_data.get("company"))

                    location = _to_str(job_data.get("location"))
                    contact, contact_type = _resolve_contact(job_data.get("contacts"), message)

                    if title and company:
                        existing_job_result = await db.execute(
                            select(Job).filter(
                                Job.title == title,
                                Job.company == company,
                            )
                        )
                        if existing_job_result.first():
                            skipped_count += 1
                            message.analysis_status = "skipped"
                            continue

                    # Fix: role_type might be a list from Ollama, convert to string
                    role_str = _to_str(job_data.get("role_type"))

                    try:
                        job = Job(
                            message_id=message.id,
                            channel_id=channel_id,
                            channel_name=channel_name,
                            confidence=confidence,
                            translated_text=translated_text,
                            title=title,
                            company=company,
                            company_link=_to_str(job_data.get("company_link")),
                            location=location,
                            is_remote=is_remote,
                            role_type=role_str,
                            skills=job_data.get("skills"),
                            contact=contact,
                            contact_type=contact_type,
                            summary=_to_str(job_data.get("summary")),
                        )
                        db.add(job)
                        jobs_added += 1
                        message.analysis_status = "analyzed"
                    except Exception as e:
                        logger.error(f"[DB ERROR] Failed to save job for msg {message.id}: {e}")
                        skipped_count += 1
                        message.analysis_status = "skipped"
                        message_results[-1]["status"] = "db_error"
                        message_results[-1]["error"] = str(e)

                # ── PERSONAL INFO ─────────────────────────────────────────────
                elif category == "personal_info":
                    pi_data = result.get("personal_info") or {}

                    name = _to_str(pi_data.get("name"))
                    contact, contact_type = _resolve_contact(pi_data.get("contacts"), message)

                    portfolio = _to_str(pi_data.get("portfolio"))
                    github = _to_str(pi_data.get("github"))
                    linkedin = _to_str(pi_data.get("linkedin"))

                    if not name:
                        name = message.sender_username or f"sender:{message.sender_id or 'unknown'}"

                    if name:
                        conditions = [Developer.name == name]
                        if contact:
                            conditions.append(Developer.contact == contact)
                        if github:
                            conditions.append(Developer.github == github)
                        if linkedin:
                            conditions.append(Developer.linkedin == linkedin)

                        if len(conditions) >= 2:
                            existing_dev_result = await db.execute(
                                select(Developer).filter(*conditions)
                            )
                            if existing_dev_result.first():
                                skipped_count += 1
                                message.analysis_status = "skipped"
                                continue

                    # Fix: experience might be a list from Ollama, convert to string with newlines
                    exp_val = pi_data.get("experience")
                    if isinstance(exp_val, list):
                        exp_str = "\n".join(str(item) for item in exp_val)
                    else:
                        exp_str = str(exp_val) if exp_val else None

                    try:
                        developer = Developer(
                            message_id=message.id,
                            channel_id=channel_id,
                            confidence=confidence,
                            translated_text=translated_text,
                            name=name,
                            skills=pi_data.get("skills"),
                            experience=exp_str,
                            portfolio=portfolio,
                            github=github,
                            linkedin=linkedin,
                            contact=contact,
                            contact_type=contact_type,
                            looking_for_work=pi_data.get("looking_for_work"),
                            summary=_to_str(pi_data.get("summary")),
                        )
                        db.add(developer)
                        devs_added += 1
                        message.analysis_status = "analyzed"
                    except Exception as e:
                        logger.error(f"[DB ERROR] Failed to save developer for msg {message.id}: {e}")
                        skipped_count += 1
                        message.analysis_status = "skipped"
                        message_results[-1]["status"] = "db_error"
                        message_results[-1]["error"] = str(e)

                else:
                    skipped_count += 1
                    message.analysis_status = "skipped"

                analyzed_count += 1

            batch_message_results = message_results[-len(filtered_messages):] if filtered_messages else []
            
            # Determine if this batch succeeded (at least one message processed without error)
            batch_has_errors = any(r.get("status") in ["failed", "db_error"] for r in batch_message_results)
            if batch_has_errors:
                consecutive_failures += 1
                logger.warning(f"[ANALYZE BATCH ERROR] Channel: {channel_username} | Batch {batch_num} had errors | Consecutive failures: {consecutive_failures}")
            else:
                consecutive_failures = 0  # Reset on success
            
            await broadcast_progress("analyze_progress", {
                "channel": channel_username,
                "channel_id": channel_id,
                "current": batch_num,
                "total": total_batches,
                "analyzed": analyzed_count,
                "total_messages": total_messages,
                "jobs": jobs_added,
                "developers": devs_added,
                "operation_id": operation_id,
                "tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens,
                },
                "message_results": batch_message_results,
            })
            
            # Update operation progress
            try:
                await update_operation(db, operation_id, current=batch_num, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)
            except Exception as e:
                logger.warning(f"[ANALYZE] Failed to update operation progress: {e}")
            
            # Commit after each batch to save progress (with error recovery)
            try:
                await db.commit()
            except Exception as e:
                logger.error(f"[ANALYZE BATCH COMMIT ERROR] Channel: {channel_username} | Batch {batch_num} commit failed: {e}")
                await db.rollback()
                # Continue anyway - next batch will try again

        try:
            await db.commit()
            logger.info(f"Commit OK — jobs: {jobs_added}, devs: {devs_added}")
        except Exception as e:
            await db.rollback()
            logger.error(f"[ANALYZE COMMIT ERROR] Channel: {channel_username} | DB commit failed: {e}")
            # Don't raise - return partial success instead
            return {
                "success": True,  # Partial success - some messages were processed
                "jobs_found": jobs_added,
                "developers_found": devs_added,
                "analyzed": analyzed_count,
                "stopped": stopped_count > 0,
                "remaining": stopped_count,
                "warning": f"Commit failed: {str(e)[:100]}",
            }

        if run_id:
            try:
                run_result = await db.execute(select(AnalysisRun).filter(AnalysisRun.id == run_id))
                run = run_result.scalar_one_or_none()
                if run:
                    run.messages_analyzed += analyzed_count
                    run.jobs_found += jobs_added
                    await db.commit()
            except Exception as e:
                logger.error(f"Error updating run stats: {e}")
                await db.rollback()

        status = "stopped" if stopped_count > 0 else "completed"
        logger.info(f"[ANALYZE COMPLETE] Channel: {channel_username} | Status: {status} | Analyzed: {analyzed_count} | Jobs: {jobs_added} | Devs: {devs_added} | Stopped: {stopped_count > 0}")
        await broadcast_progress("analyze_complete", {
            "channel": channel_username,
            "channel_id": channel_id,
            "analyzed": analyzed_count,
            "jobs": jobs_added,
            "developers": devs_added,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
            "operation_id": operation_id,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
        })
        await update_operation(db, operation_id, status=status, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)

        return {
            "success": True,
            "analyzed": analyzed_count,
            "jobs_found": jobs_added,
            "developers_found": devs_added,
            "skipped": skipped_count,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
        }

    except Exception as e:
        await db.rollback()
        await update_operation(db, operation_id, status="error", error_message=str(e))
        # Broadcast error to frontend so it clears the UI
        await broadcast_progress("error", {
            "channel": channel_username,
            "channel_id": channel_id,
            "operation_id": operation_id,
            "error": str(e),
        })
        logger.error(f"[ANALYZE ERROR] Channel: {channel_username} | Error: {e}")
        return {"success": False, "error": str(e)}

    finally:
        cleanup_stop_event(channel_id)


# ── CRON ──────────────────────────────────────────────────────────────────────

async def continuous_scanner(
    fetch_interval_minutes: int = 30,
    sleep_interval_seconds: int = 30,
) -> None:
    """Continuously fetch and analyze messages from channels."""
    global cron_running

    channel_index = 0
    last_fetch_time: dict[int, datetime] = {}

    while cron_running:
        try:
            async with AsyncSessionLocal() as db:
                try:
                    channels_result = await db.execute(select(Channel).filter(Channel.is_active == True))
                    channels = channels_result.scalars().all()

                    if not channels:
                        await asyncio.sleep(sleep_interval_seconds)
                        continue

                    channel = channels[channel_index % len(channels)]
                    channel_index += 1
                    channel_id = channel.id

                    now = datetime.now(timezone.utc)
                    last = last_fetch_time.get(channel_id)
                    due = last is None or (now - last).total_seconds() >= fetch_interval_minutes * 60

                    if due:
                        try:
                            fetch_result = await fetch_and_store_messages(db, channel, days_back=1)
                            if fetch_result["success"]:
                                last_fetch_time[channel_id] = now
                                if fetch_result["new_stored"] > 0:
                                    try:
                                        await analyze_messages(db, channel)
                                    except Exception as e:
                                        logger.error(f"Analyze error in cron: {e}")
                        except Exception as e:
                            logger.error(f"Fetch error in cron: {e}")

                except Exception as e:
                    logger.error(f"Cron inner error: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cron outer error: {e}")

        await asyncio.sleep(sleep_interval_seconds)


async def analyze_website_posts(
    db: AsyncSession,
    website_source: WebsiteSource,
    bulk_operation_id: Optional[str] = None,
) -> dict:
    """Analyze unanalyzed website posts with AI using RSS extraction with batching and circuit breaker."""
    # Capture primitives immediately
    source_id = website_source.id
    source_name = website_source.name
    source_url = website_source.url
    custom_prompt = website_source.extraction_prompt
    site_type = website_source.site_type

    if not await is_ollama_available():
        return {"success": False, "error": "Ollama not available"}

    try:
        messages_result = await db.execute(
            select(Message).filter(
                Message.website_source_id == source_id,
                Message.analysis_status == "pending",
            )
        )
        messages = messages_result.scalars().all()
        total_messages = len(messages)

        operation_id = await create_operation(db, "analyze", None, total_messages=total_messages, bulk_operation_id=bulk_operation_id)
        await update_operation(db, operation_id, channel_username=source_name, total_messages=total_messages)

        # Reset stop event
        reset_website_stop_event(source_id)

        # Broadcast start
        await broadcast_progress("analyze_start", {
            "channel": source_name,
            "channel_id": source_id,
            "operation_id": operation_id,
        })

        if len(messages) == 0:
            await update_operation(db, operation_id, status="completed")
            cleanup_website_stop_event(source_id)
            return {"success": True, "analyzed": 0, "jobs_found": 0, "developers_found": 0, "skipped": 0}

        # Use RSS extractor for website sources
        from web_crawler import Extractor
        extractor = Extractor()

        jobs_added = 0
        devs_added = 0
        skipped_count = 0
        analyzed_count = 0
        stopped_count = 0
        batch_size = 3
        total_batches = (total_messages + batch_size - 1) // batch_size

        # Circuit breaker: stop after too many consecutive batch failures
        consecutive_failures = 0
        max_consecutive_failures = 5

        prompt_type = "custom" if custom_prompt else (site_type or "generic")
        logger.info(f"[ANALYZE WEBSITE] ▶ START | source={source_name} | url={source_url} | pending_messages={total_messages} | batches={total_batches} | batch_size={batch_size} | model={extractor.model} | prompt={prompt_type}")

        for batch_num in range(total_batches):
            # Check for stop signal
            if is_website_operation_stopped(source_id):
                logger.info(f"[ANALYZE WEBSITE STOP] Source: {source_name} - Stop signal received")
                stopped_count = total_messages - (batch_num * batch_size)
                break

            if consecutive_failures >= max_consecutive_failures:
                logger.error(f"[ANALYZE WEBSITE CIRCUIT BREAKER] Source: {source_name} - Stopping after {consecutive_failures} consecutive batch failures")
                stopped_count = total_messages - (batch_num * batch_size)
                break

            batch_start = batch_num * batch_size
            batch_end = min(batch_start + batch_size, total_messages)
            filtered_messages = messages[batch_start:batch_end]

            logger.info(f"[ANALYZE WEBSITE BATCH] Source: {source_name} | Batch {batch_num + 1}/{total_batches} | Messages {batch_start + 1}-{batch_end}")

            batch_message_results = []
            for message in filtered_messages:
                msg_preview = (message.text or '')[:120].replace('\n', ' ')
                logger.info(f"[ANALYZE WEBSITE MSG] id={message.id} | preview={msg_preview!r}")
                try:
                    # Use RSS extractor with custom prompt if provided
                    extracted_data = await extractor.extract(
                        message.text,
                        source_url,
                        custom_prompt=custom_prompt,
                        site_type=site_type,
                    )
                    logger.info(f"[ANALYZE WEBSITE MSG RESULT] id={message.id} | jobs={len(extracted_data.job_postings)} | developer={'yes' if extracted_data.developer_info else 'no'}")

                    # Process extracted job postings
                    for job in extracted_data.job_postings:
                        # Check if job already exists for this message
                        existing_job = await db.execute(
                            select(Job).filter(Job.message_id == message.id)
                        )
                        if existing_job.scalar_one_or_none():
                            continue

                        # Create job from extracted data (map to valid Job model fields)
                        job_obj = Job(
                            message_id=message.id,
                            website_source_id=source_id,
                            channel_name=source_name,
                            title=job.title or "Unknown",
                            company=job.company or "Unknown",
                            location=job.location,
                            is_remote=job.is_remote,
                            company_link=job.url,
                            summary=job.requirements,
                        )
                        db.add(job_obj)
                        jobs_added += 1
                        logger.info(f"[ANALYZE WEBSITE JOB SAVED] msg_id={message.id} | title={job_obj.title!r} | company={job_obj.company!r} | remote={job_obj.is_remote}")

                    # Process developer info if present
                    if extracted_data.developer_info:
                        dev = extracted_data.developer_info
                        existing_dev = await db.execute(
                            select(Developer).filter(
                                Developer.website_source_id == source_id,
                                Developer.name == dev.team_name
                            )
                        )
                        if not existing_dev.first():
                            dev_obj = Developer(
                                website_source_id=source_id,
                                name=dev.team_name,
                                skills=dev.tech_stack,
                                portfolio=dev.open_source_links[0] if dev.open_source_links else None,
                                summary=dev.description,
                            )
                            db.add(dev_obj)
                            devs_added += 1

                    message.analysis_status = "analyzed"
                    analyzed_count += 1
                    batch_message_results.append({"status": "success"})
                    logger.info(f"[ANALYZE WEBSITE MSG OK] id={message.id} | status=analyzed | jobs_total={jobs_added}")

                except Exception as e:
                    logger.error(f"[ANALYZE WEBSITE] Error analyzing message {message.id}: {e}", exc_info=True)
                    message.analysis_status = "error"
                    batch_message_results.append({"status": "failed", "error": str(e)})
                    continue

            # Determine if this batch succeeded
            batch_has_errors = any(r.get("status") in ["failed", "db_error"] for r in batch_message_results)
            if batch_has_errors:
                consecutive_failures += 1
                logger.warning(f"[ANALYZE WEBSITE BATCH ERROR] Source: {source_name} | Batch {batch_num + 1} had errors | Consecutive failures: {consecutive_failures}")
            else:
                consecutive_failures = 0

            # Broadcast progress
            await broadcast_progress("analyze_progress", {
                "channel": source_name,
                "channel_id": source_id,
                "current": batch_num + 1,
                "total": total_batches,
                "analyzed": analyzed_count,
                "total_messages": total_messages,
                "jobs": jobs_added,
                "developers": devs_added,
                "operation_id": operation_id,
            })

            try:
                await update_operation(db, operation_id, current=batch_num + 1, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)
            except Exception as e:
                logger.warning(f"[ANALYZE WEBSITE] Failed to update operation progress: {e}")

            try:
                await db.commit()
            except Exception as e:
                logger.error(f"[ANALYZE WEBSITE BATCH COMMIT ERROR] Source: {source_name} | Batch {batch_num + 1} commit failed: {e}")
                await db.rollback()

        try:
            await db.commit()
            logger.info(f"[ANALYZE WEBSITE] Commit OK — jobs: {jobs_added}, devs: {devs_added}")
        except Exception as e:
            await db.rollback()
            logger.error(f"[ANALYZE WEBSITE COMMIT ERROR] Source: {source_name} | DB commit failed: {e}")
            return {
                "success": True,
                "jobs_found": jobs_added,
                "developers_found": devs_added,
                "analyzed": analyzed_count,
                "stopped": stopped_count > 0,
                "remaining": stopped_count,
                "warning": f"Commit failed: {str(e)[:100]}",
            }

        status = "stopped" if stopped_count > 0 else "completed"
        await update_operation(db, operation_id, status=status)
        
        # Broadcast completion
        await broadcast_progress("analyze_complete", {
            "channel": source_name,
            "channel_id": source_id,
            "analyzed": analyzed_count,
            "jobs": jobs_added,
            "developers": devs_added,
            "operation_id": operation_id,
        })

        logger.info(f"[ANALYZE WEBSITE] ✓ COMPLETE | source={source_name} | analyzed={analyzed_count}/{total_messages} | jobs_saved={jobs_added} | devs_saved={devs_added} | skipped={skipped_count} | status={status}")
        return {
            "success": True,
            "analyzed": analyzed_count,
            "jobs_found": jobs_added,
            "developers_found": devs_added,
            "skipped": skipped_count,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
        }

    except Exception as e:
        logger.error(f"[ANALYZE WEBSITE] Error: {e}", exc_info=True)
        # Broadcast error
        await broadcast_progress("error", {
            "channel": source_name,
            "channel_id": source_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}
    finally:
        cleanup_website_stop_event(source_id)


# ── LIFESPAN ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown events."""
    # Cleanup stale operations on startup
    await cleanup_stale_operations()
    try:
        yield
    finally:
        await stop_cron_task()