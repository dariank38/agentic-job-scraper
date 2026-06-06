"""Background tasks and helper functions for job scraping."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal, get_db, manager
from app.models import AnalysisRun, Channel, Developer, Job, Message
from telegram_processor import TelegramClientManager, fetch_messages
from services.ollama_service import get_analyzer, is_ollama_available

logger = logging.getLogger(__name__)

# Global stop events for cancelling analysis (per-channel)
analysis_stop_events: dict[int, asyncio.Event] = {}

# Cron job state
cron_running = False
cron_task: asyncio.Task | None = None


def reset_stop_event(channel_id: int):
    """Reset the stop event for a specific channel before starting analysis."""
    analysis_stop_events[channel_id] = asyncio.Event()


def stop_analysis(channel_id: int):
    """Signal the analysis for a specific channel to stop."""
    if channel_id in analysis_stop_events:
        analysis_stop_events[channel_id].set()
        print(f"[Analyze] Stop signal received for channel {channel_id}")


def is_analysis_stopped(channel_id: int) -> bool:
    """Check if analysis for a specific channel has been stopped."""
    return analysis_stop_events.get(channel_id, asyncio.Event()).is_set()


def is_cron_running() -> bool:
    """Check if the cron job is currently running."""
    return cron_running


def start_cron_task() -> bool:
    """Start the continuous scanner background task."""
    global cron_running, cron_task
    if cron_running:
        return False
    cron_running = True
    cron_task = asyncio.create_task(continuous_scanner())
    print("[Cron] Started continuous scanner")
    return True


def stop_cron_task() -> bool:
    """Stop the continuous scanner background task."""
    global cron_running, cron_task
    if not cron_running:
        return False
    cron_running = False
    if cron_task:
        cron_task.cancel()
        cron_task = None
    print("[Cron] Stopped continuous scanner")
    return True


async def broadcast_progress(event_type: str, data: dict):
    """Broadcast progress update to all WebSocket clients."""
    try:
        await manager.broadcast({"type": event_type, **data})
    except Exception as e:
        print(f"[Broadcast] Error sending progress: {e}")


async def fetch_and_store_messages(
    db: AsyncSession,
    channel: Channel,
    days_back: int = 10,
    run_id: Optional[int] = None,
) -> dict:
    """Fetch messages from Telegram and store in database."""
    # BUG FIX #1: Renamed to telegram_manager to avoid shadowing the global WebSocket `manager`
    telegram_manager = TelegramClientManager()

    try:
        print(f"[Fetch] Starting fetch for {channel.username} (days_back={days_back})")
        await broadcast_progress("fetch_start", {"channel": channel.username, "days_back": days_back})
        await telegram_manager.connect()

        print(f"[Fetch] Fetching messages from {channel.username}...")
        await broadcast_progress("fetch_progress", {"channel": channel.username, "status": "fetching"})
        messages = await fetch_messages(
            telegram_manager.client,
            channel.username,
            days_back=days_back,
        )
        print(f"[Fetch] Fetched {len(messages)} messages from {channel.username}")
        await broadcast_progress("fetch_progress", {"channel": channel.username, "status": "fetched", "count": len(messages)})

        new_count = 0
        for i, msg_data in enumerate(messages):
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

                message = Message(
                    telegram_id=msg_data["id"],
                    channel_id=channel.id,
                    date=msg_data.get("date"),
                    text=msg_data.get("text"),
                    sender_id=msg_data.get("sender_id"),
                    sender_username=sender.get("username"),
                    sender_first_name=sender.get("first_name"),
                    has_image=msg_data.get("has_image", False),
                )
                db.add(message)
                await db.flush()
                new_count += 1

                if (i + 1) % 10 == 0:
                    print(f"[Fetch] Processed {i + 1}/{len(messages)} messages for {channel.username}, {new_count} new")
                    await broadcast_progress("fetch_progress", {"channel": channel.username, "processed": i + 1, "total": len(messages), "new": new_count})

            except Exception as e:
                print(f"[Fetch] Error storing message {msg_data.get('id')}: {e}")
                await db.rollback()
                # BUG FIX #2: Removed manual begin() — SQLAlchemy async uses autobegin,
                # calling begin() after rollback raises InvalidRequestError
                continue

        await db.commit()
        print(f"[Fetch] Stored {new_count} new messages for {channel.username}")
        await broadcast_progress("fetch_complete", {"channel": channel.username, "new_messages": new_count})

        if run_id:
            try:
                result = await db.execute(select(AnalysisRun).filter(AnalysisRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.messages_fetched += len(messages)
                    await db.commit()
            except Exception as e:
                print(f"[Fetch] Error updating run stats: {e}")
                await db.rollback()

        return {
            "success": True,
            "fetched": len(messages),
            "new_stored": new_count,
        }

    except Exception as e:
        await db.rollback()
        error_msg = str(e).lower()
        invalid_channel_errors = [
            "channel not found",
            "channel invalid",
            "username not occupied",
            "username invalid",
            "no such entity",
            "private",
            "forbidden",
        ]

        if any(err in error_msg for err in invalid_channel_errors):
            print(f"[Fetch] Channel {channel.username} is invalid/non-existent, removing from DB")
            try:
                await db.delete(channel)
                await db.commit()
            except Exception as delete_error:
                print(f"[Fetch] Error deleting channel: {delete_error}")
                await db.rollback()
            return {
                "success": False,
                "error": f"Channel removed: {str(e)}",
                "channel_removed": True,
            }

        print(f"[Fetch] Error fetching {channel.username}: {e}")
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        try:
            await telegram_manager.disconnect()
        except Exception:
            pass


def should_analyze_message(text: str) -> bool:
    """Quick keyword pre-filter to avoid sending irrelevant messages to Ollama."""
    text_lower = text.lower()

    inclusion_keywords = [
        # English
        "software", "developer", "programmer", "engineer",
        "backend", "frontend", "fullstack", "full-stack", "full stack",
        "devops", "mobile", "blockchain", "smart contract",
        "qa", "tester", "testing", "automation",
        "data", "machine learning", "ml engineer", "ai engineer",
        "python", "javascript", "typescript", "react", "node",
        "golang", "rust", "java", "kotlin", "swift",
        "hiring", "we are looking", "job opening", "vacancy",
        "cv", "resume", "portfolio", "github",
        "looking for work", "open to work", "available for", "remote work",
        "php", "laravel", "django", "flask",
        "docker", "kubernetes", "aws", "cloud",
        "sql", "database", "api", "microservices",
        "web3", "solidity", "defi", "dapp",
        "flutter", "react native", "ios", "android",
        "team lead", "tech lead", "architect", "cto",
        "junior", "senior", "mid-level", "lead",
        "scala", "elixir", "ruby", "rails",
        # Chinese
        "软件", "开发", "程序员", "工程师",
        "后端", "前端", "全栈", "运维", "测试",
        "移动", "区块链", "智能合约",
        "数据", "机器学习", "人工智能",
        "招聘", "急聘", "诚聘", "招", " hiring ",
        "求职", "找工作", "简历", "portfolio", "github",
        "远程", "居家办公", "在家办公",
        "php", "laravel", "python", "java",
        "docker", "kubernetes", "云", "数据库",
        "web3", "solidity",
        "flutter", "react native", "安卓", "ios",
        "技术负责人", "架构师", "总监",
        "初级", "中级", "高级", "资深",
    ]

    for keyword in inclusion_keywords:
        if keyword in text_lower:
            return True

    exclusion_keywords = [
        "marketing", "seo", "digital marketing", "promotion",
        "advertising", "sales", "affiliate", "dropshipping",
        "mlm", "crypto investment", "forex", "trading signals",
        "airdrop", "casino", "gambling", "betting",
        "medical", "healthcare", "nursing", "doctor",
        "accountant", "accounting", "finance manager",
        "hr manager", "human resources", "recruiter",
        "teacher", "tutor", "content writer", "copywriter",
        "graphic designer", "ui/ux designer", "designer only",
        "community manager", "social media manager",
        "real estate", "property", "construction",
        "driver", "delivery", "cleaning",
        # Chinese exclusion
        "营销", "推广", "广告", "销售", "微商",
        "投资", "外汇", "赌博", "博彩",
        "医疗", "护士", "医生", "会计",
        "财务", "人力资源", "人事", "招聘专员",
        "新媒体运营", "内容运营", "运营专员", "社群运营",
        "文案", "编辑", "设计", "客服",
        "房产", "建筑", "司机", "快递",
    ]

    for keyword in exclusion_keywords:
        if keyword in text_lower:
            return False

    return True


# BUG FIX #5: Moved analyze_single out of the loop to avoid per-batch redefinition
async def _analyze_single(analyzer, message):
    """Analyze a single message, returning (message, result, error)."""
    try:
        result = await analyzer.analyze_message(message.text)
        return message, result, None
    except Exception as e:
        print(f"[Analyze] Error analyzing message {message.id}: {e}")
        return message, None, e


async def analyze_messages(
    db: AsyncSession,
    channel: Channel,
    run_id: Optional[int] = None,
) -> dict:
    """Analyze unanalyzed messages with AI using concurrent pipeline."""
    if not await is_ollama_available():
        print(f"[Analyze] Ollama not available, skipping {channel.username}")
        return {
            "success": False,
            "error": "Ollama not available",
        }

    try:
        print(f"[Analyze] Starting concurrent analysis for {channel.username}")
        reset_stop_event(channel.id)
        await broadcast_progress("analyze_start", {"channel": channel.username, "channel_id": channel.id})

        messages_result = await db.execute(
            select(Message).filter(
                Message.channel_id == channel.id,
            ).outerjoin(Job).outerjoin(Developer).filter(
                (Job.id == None) & (Developer.id == None),
            )
        )
        messages = messages_result.scalars().all()
        print(f"[Analyze] Found {len(messages)} unanalyzed messages for {channel.username}")
        await broadcast_progress("analyze_progress", {"channel": channel.username, "status": "found", "total": len(messages)})

        if len(messages) == 0:
            return {"success": True, "analyzed": 0, "jobs_found": 0, "developers_found": 0, "skipped": 0}

        analyzer = get_analyzer()

        jobs_added = 0
        devs_added = 0
        skipped_count = 0
        analyzed_count = 0
        stopped_count = 0
        total_messages = len(messages)
        # batch_size aligned with analyzer semaphore max_concurrent=3
        batch_size = 3

        logger.info(f"Analyzing {total_messages} messages in batches of {batch_size} with stop support")

        for batch_start in range(0, total_messages, batch_size):
            if is_analysis_stopped(channel.id):
                print(f"[Analyze] Stop requested for channel {channel.id}, halting after batch {batch_start // batch_size}")
                stopped_count = total_messages - batch_start
                break

            batch = messages[batch_start:batch_start + batch_size]
            print(f"[Analyze] Processing batch {batch_start // batch_size + 1}: messages {batch_start + 1}-{min(batch_start + batch_size, total_messages)}")

            filtered_messages = []
            for msg in batch:
                if msg.text and should_analyze_message(msg.text):
                    filtered_messages.append(msg)
                else:
                    skipped_count += 1
                    msg.analysis_status = "skipped"

            if not filtered_messages:
                print(f"[Analyze] Batch {batch_start // batch_size + 1}: all messages filtered out")
                continue

            # BUG FIX #5: Use module-level _analyze_single instead of inner closure
            tasks = [_analyze_single(analyzer, msg) for msg in filtered_messages]
            completed = await asyncio.gather(*tasks)

            for message, result, error in completed:
                if error:
                    skipped_count += 1
                    message.analysis_status = "skipped"
                    continue

                if not result or result.get("category") == "other":
                    skipped_count += 1
                    message.analysis_status = "skipped"
                    continue

                category = result.get("category", "other")
                confidence = result.get("confidence")
                translated_text = result.get("translated_text")

                if category == "job_posting" and result.get("job_posting"):
                    job_data = result.get("job_posting", {})
                    is_remote = job_data.get("is_remote")
                    if is_remote is False:
                        print(f"[Analyze] Skipping on-site job: {job_data.get('title', 'unknown')}")
                        skipped_count += 1
                        message.analysis_status = "skipped"
                        continue

                    job = Job(
                        message_id=message.id,
                        channel_id=channel.id,
                        confidence=confidence,
                        translated_text=translated_text,
                        title=job_data.get("title"),
                        company=job_data.get("company"),
                        company_link=job_data.get("company_link"),
                        location=job_data.get("location"),
                        is_remote=is_remote,
                        role_type=job_data.get("role_type"),
                        # BUG FIX #6: JSON column must receive list directly, not json.dumps()
                        # Storing json.dumps() causes double-serialization: "[\"python\"]" instead of ["python"]
                        skills=job_data.get("skills", []),
                        contact=job_data.get("contact"),
                        contact_type=job_data.get("contact_type"),
                        summary=job_data.get("summary"),
                    )
                    db.add(job)
                    jobs_added += 1
                    message.analysis_status = "analyzed"
                    print(f"[Analyze] Staged job: {job_data.get('title', 'unknown')}")

                elif category == "personal_info" and result.get("personal_info"):
                    pi_data = result.get("personal_info", {})
                    developer = Developer(
                        message_id=message.id,
                        channel_id=channel.id,
                        confidence=confidence,
                        translated_text=translated_text,
                        name=pi_data.get("name"),
                        # BUG FIX #6: Same double-serialization fix for Developer.skills
                        skills=pi_data.get("skills", []),
                        experience=pi_data.get("experience"),
                        portfolio=pi_data.get("portfolio"),
                        github=pi_data.get("github"),
                        linkedin=pi_data.get("linkedin"),
                        contact=pi_data.get("contact"),
                        contact_type=pi_data.get("contact_type"),
                        looking_for_work=pi_data.get("looking_for_work"),
                        summary=pi_data.get("summary"),
                    )
                    db.add(developer)
                    devs_added += 1
                    message.analysis_status = "analyzed"
                    print(f"[Analyze] Staged developer: {pi_data.get('name', 'unknown')}")
                else:
                    skipped_count += 1
                    message.analysis_status = "skipped"

                analyzed_count += 1

            processed = min(batch_start + batch_size, total_messages)
            await broadcast_progress("analyze_progress", {
                "channel": channel.username,
                "channel_id": channel.id,
                "processed": processed,
                "total": total_messages,
                "analyzed": analyzed_count,
                "jobs": jobs_added,
                "developers": devs_added,
            })

        try:
            await db.commit()
            logger.info(f"Database commit successful. Jobs found: {jobs_added}, Developers found: {devs_added}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Database write transaction failed: {str(e)}")
            raise e

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

        stop_note = f" (stopped {stopped_count} remaining)" if stopped_count > 0 else ""
        print(f"[Analyze] Completed analysis for {channel.username}{stop_note}: {analyzed_count} analyzed, {jobs_added} jobs, {devs_added} developers, {skipped_count} skipped")
        await broadcast_progress("analyze_complete", {
            "channel": channel.username,
            "channel_id": channel.id,
            "analyzed": analyzed_count,
            "jobs": jobs_added,
            "developers": devs_added,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
        })

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
        print(f"[Analyze] Error in analyze_messages for {channel.username}: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def continuous_scanner(
    fetch_interval_minutes: int = 30,
    sleep_interval_seconds: int = 30,
) -> None:
    """Continuously fetch messages from channels (fetch-only, no analysis)."""
    global cron_running
    print(f"[Cron] Starting continuous scanner (fetch-only)")

    channel_index = 0
    last_fetch_time: dict[int, datetime] = {}

    while cron_running:
        try:
            async with AsyncSessionLocal() as db:
                try:
                    channels_result = await db.execute(select(Channel).filter(Channel.is_active == True))
                    channels = channels_result.scalars().all()

                    if not channels:
                        print("[Cron] No active channels configured, waiting...")
                        await asyncio.sleep(sleep_interval_seconds)
                        continue

                    channel = channels[channel_index % len(channels)]
                    channel_index += 1

                    now = datetime.now()
                    last = last_fetch_time.get(channel.id)
                    due = last is None or (now - last).total_seconds() >= fetch_interval_minutes * 60

                    if due:
                        print(f"[Cron] Fetching {channel.username}...")
                        try:
                            fetch_result = await fetch_and_store_messages(db, channel, days_back=1)
                            if fetch_result["success"]:
                                last_fetch_time[channel.id] = now
                                print(f"[Cron] {channel.username}: fetched {fetch_result['fetched']}, new {fetch_result['new_stored']}")
                            else:
                                print(f"[Cron] {channel.username}: fetch ERROR - {fetch_result.get('error', 'unknown')}")
                        except Exception as e:
                            print(f"[Cron] {channel.username}: fetch EXCEPTION - {e}")
                    else:
                        mins_left = int((fetch_interval_minutes * 60 - (now - last).total_seconds()) / 60)
                        print(f"[Cron] {channel.username}: next fetch in ~{mins_left}m, nothing to do")

                except Exception as e:
                    print(f"[Cron] Loop ERROR: {e}")

        except asyncio.CancelledError:
            print("[Cron] Task cancelled")
            break
        except Exception as e:
            print(f"[Cron] CRITICAL ERROR: {e}")

        await asyncio.sleep(sleep_interval_seconds)

    print("[Cron] Continuous scanner stopped")


@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown events."""
    yield