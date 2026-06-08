"""Background tasks and helper functions for job scraping."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal, get_db, manager
from app.models import AnalysisRun, Channel, Developer, Job, Message, Operation, TelegramAccount
from telegram_processor import TelegramClientManager, fetch_messages
from services.ollama_service import get_analyzer, is_ollama_available, should_analyze_message

logger = logging.getLogger(__name__)

# Global stop events for cancelling analysis (per-channel)
analysis_stop_events: dict[int, asyncio.Event] = {}

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


def reset_bulk_stop_event(operation_id: str):
    """Reset stop event for a bulk operation."""
    bulk_stop_events[operation_id] = asyncio.Event()


def stop_bulk_operation(operation_id: str):
    """Signal bulk operation to stop."""
    if operation_id in bulk_stop_events:
        bulk_stop_events[operation_id].set()


def is_bulk_operation_stopped(operation_id: str) -> bool:
    """Check if bulk operation should stop."""
    event = bulk_stop_events.get(operation_id)
    if event is None:
        return False
    return event.is_set()


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
    channel: Channel,
    total_messages: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> int:
    operation = Operation(
        operation_type=operation_type,
        channel_id=channel.id,
        channel_username=channel.username,
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
    commit: bool = True,
):
    """Update operation progress. Use commit=False to batch updates."""
    result = await db.execute(select(Operation).filter(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if operation:
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
        if developers_found is not None:
            operation.developers_found = developers_found
        if error_message is not None:
            operation.error_message = error_message
        if status in ("completed", "stopped", "error"):
            operation.completed_at = datetime.utcnow()
        if commit:
            await db.commit()


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
    """Convert list or value to comma-separated string."""
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v) or None
    return str(value)


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
    days_back: int = 10,
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

async def _analyze_single(analyzer, message):
    """Analyze a single message, returning (message, result, error)."""
    try:
        result = await asyncio.wait_for(
            analyzer.analyze_message(message.text),
            timeout=120,
        )
        return message, result, None
    except asyncio.TimeoutError:
        return message, None, Exception("Analysis timeout")
    except Exception as e:
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

        logger.info(f"Analyzing {total_messages} messages in {total_batches} batches of {batch_size}")

        for batch_num, batch_start in enumerate(range(0, total_messages, batch_size), 1):
            # Check both individual channel stop and bulk operation stop
            if is_analysis_stopped(channel_id) or (bulk_operation_id and is_bulk_operation_stopped(bulk_operation_id)):
                stopped_count = total_messages - batch_start
                break

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

            tasks = [_analyze_single(analyzer, msg) for msg in filtered_messages]
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

                category = result.get("category")
                confidence = result.get("confidence")
                translated_text = result.get("translated_text")

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

                    is_remote = job_data.get("is_remote")
                    if is_remote is False:
                        # On-site only — not relevant for this board
                        skipped_count += 1
                        message.analysis_status = "skipped"
                        continue

                    title = job_data.get("title")
                    company = job_data.get("company")

                    location = _to_str(job_data.get("location"))
                    contact, contact_type = _resolve_contact(job_data.get("contacts"), message)

                    if not title:
                        title = f"[No Title] sender:{message.sender_username or message.sender_id or 'unknown'}"

                    if title and company:
                        existing_job_result = await db.execute(
                            select(Job).filter(
                                Job.title == title,
                                Job.company == company,
                            )
                        )
                        if existing_job_result.scalar_one_or_none():
                            skipped_count += 1
                            message.analysis_status = "skipped"
                            continue

                    job = Job(
                        message_id=message.id,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        confidence=confidence,
                        translated_text=translated_text,
                        title=title,
                        company=company,
                        company_link=job_data.get("company_link"),
                        location=location,
                        is_remote=is_remote,
                        role_type=job_data.get("role_type"),
                        skills=job_data.get("skills", []),
                        contact=contact,
                        contact_type=contact_type,
                        summary=job_data.get("summary"),
                    )
                    db.add(job)
                    jobs_added += 1
                    message.analysis_status = "analyzed"

                # ── PERSONAL INFO ─────────────────────────────────────────────
                elif category == "personal_info":
                    pi_data = result.get("personal_info") or {}

                    name = pi_data.get("name")
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
                            if existing_dev_result.scalar_one_or_none():
                                skipped_count += 1
                                message.analysis_status = "skipped"
                                continue

                    developer = Developer(
                        message_id=message.id,
                        channel_id=channel_id,
                        confidence=confidence,
                        translated_text=translated_text,
                        name=name,
                        skills=pi_data.get("skills", []),
                        experience=pi_data.get("experience"),
                        portfolio=portfolio,
                        github=github,
                        linkedin=linkedin,
                        contact=contact,
                        contact_type=contact_type,
                        looking_for_work=pi_data.get("looking_for_work"),
                        summary=pi_data.get("summary"),
                    )
                    db.add(developer)
                    devs_added += 1
                    message.analysis_status = "analyzed"

                else:
                    skipped_count += 1
                    message.analysis_status = "skipped"

                analyzed_count += 1

            batch_message_results = message_results[-len(filtered_messages):] if filtered_messages else []
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
            await update_operation(db, operation_id, current=batch_num, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)

        try:
            await db.commit()
            logger.info(f"Commit OK — jobs: {jobs_added}, devs: {devs_added}")
        except Exception as e:
            await db.rollback()
            logger.error(f"DB commit failed: {e}")
            raise

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


# ── LIFESPAN ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown events."""
    try:
        yield
    finally:
        await stop_cron_task()