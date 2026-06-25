"""Continuous scanner (cron), cleanup tasks, and app lifespan."""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal
from app.models import Channel, Message, WebsiteSource
from services.ollama_service import get_analyzer, is_ollama_available
from app.autonomous.budget_guard import OllamaBudgetGuard
from app.autonomous.state_manager import AutonomousStateManager
from app.tasks.fetch import fetch_and_store_messages, record_fetch_outcome
from app.tasks.analyze import analyze_messages, analyze_website_posts

logger = logging.getLogger(__name__)

# Cron job state
cron_running = False
cron_task: asyncio.Task | None = None
_cron_lock = asyncio.Lock()

# Global auto-analyze preference
_auto_analyze_enabled = False

# Module-level cache for source intervals
_source_intervals: dict[tuple[str, int], int] = {}


def is_cron_running() -> bool:
    return cron_running


def get_auto_analyze() -> bool:
    return _auto_analyze_enabled


def set_auto_analyze(enabled: bool) -> None:
    global _auto_analyze_enabled
    _auto_analyze_enabled = enabled


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


def refresh_source_intervals() -> None:
    global _source_intervals
    _source_intervals.clear()


async def cleanup_old_messages():
    from app.models import Job, Developer
    from sqlalchemy.orm import selectinload

    async with AsyncSessionLocal() as db:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=2)
            result = await db.execute(
                select(Message).options(
                    selectinload(Message.job),
                    selectinload(Message.developer)
                ).filter(Message.date < cutoff_date)
            )
            old_messages = result.scalars().all()
            if not old_messages:
                return

            deleted_count = 0
            for msg in old_messages:
                if msg.job and msg.job.is_applied:
                    continue
                if msg.developer and msg.developer.is_contacted:
                    continue
                await db.delete(msg)
                deleted_count += 1

            await db.commit()
        except Exception:
            await db.rollback()


async def continuous_scanner(
    fetch_interval_minutes: int = 30,
    sleep_interval_seconds: int = 30,
) -> None:
    global cron_running, _source_intervals

    channel_index = 0
    website_index = 0
    last_fetch_time: dict[int, datetime] = {}
    last_website_fetch_time: dict[int, datetime] = {}

    async def get_source_interval(db, source_type: str, source_id: int) -> int:
        cache_key = (source_type, source_id)
        if cache_key in _source_intervals:
            return _source_intervals[cache_key]
        try:
            from app.models import SourceScoring
            result = await db.execute(
                select(SourceScoring).filter(
                    SourceScoring.source_id == source_id,
                    SourceScoring.source_type == source_type,
                )
            )
            scoring = result.scalar_one_or_none()
            if scoring and scoring.recommended_interval_minutes:
                _source_intervals[cache_key] = scoring.recommended_interval_minutes
                return scoring.recommended_interval_minutes
        except Exception:
            pass
        _source_intervals[cache_key] = fetch_interval_minutes
        return fetch_interval_minutes

    while cron_running:
        try:
            async with AsyncSessionLocal() as db:
                try:
                    channels_result = await db.execute(
                        select(Channel).filter(Channel.is_active == True, Channel.is_listened == False)
                    )
                    channels = channels_result.scalars().all()

                    if channels:
                        channel = channels[channel_index % len(channels)]
                        channel_index += 1
                        channel_id = channel.id

                        now = datetime.now(timezone.utc)
                        last = last_fetch_time.get(channel_id)
                        interval_minutes = await get_source_interval(db, "telegram", channel_id)
                        due = last is None or (now - last).total_seconds() >= interval_minutes * 60

                        if due:
                            try:
                                fetch_result = await fetch_and_store_messages(db, channel, days_back=1)
                                if fetch_result["success"]:
                                    last_fetch_time[channel_id] = now
                                    try:
                                        await analyze_messages(db, channel)
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                    from web_crawler import Fetcher
                    from web_crawler.config import DEFAULT_DAYS_BACK as WEB_DAYS_BACK

                    website_sources_result = await db.execute(select(WebsiteSource).filter(WebsiteSource.is_active == True))
                    website_sources = website_sources_result.scalars().all()

                    if website_sources:
                        website = website_sources[website_index % len(website_sources)]
                        website_index += 1
                        website_id = website.id

                        now = datetime.now(timezone.utc)
                        last_website = last_website_fetch_time.get(website_id)
                        interval_minutes = await get_source_interval(db, "website", website_id)
                        website_due = last_website is None or (now - last_website).total_seconds() >= interval_minutes * 60

                        if website_due:
                            fetch_start = datetime.now()
                            fetch_error = None
                            new_jobs_count = 0

                            try:
                                if website.site_type == "bossjob":
                                    from web_crawler import fetch_posts
                                    analyzer = None
                                    budget_guard = None
                                    state_manager = None
                                    if await is_ollama_available():
                                        analyzer = get_analyzer()
                                        budget_guard = OllamaBudgetGuard(db)
                                        state_manager = AutonomousStateManager(db)
                                        await budget_guard.initialize()
                                    posts = await fetch_posts(
                                        website.url,
                                        site_type="bossjob",
                                        days_back=WEB_DAYS_BACK,
                                        analyzer=analyzer,
                                        budget_guard=budget_guard,
                                        state_manager=state_manager,
                                    )
                                    rss_entries = [
                                        {
                                            "text": post.get("text", ""),
                                            "link": post.get("url", ""),
                                            "published": post.get("date").isoformat() if post.get("date") else None,
                                        }
                                        for post in posts
                                    ]
                                else:
                                    crawler = Fetcher()
                                    fetch_result = await crawler.fetch(website.url, days_back=WEB_DAYS_BACK)
                                    rss_entries = fetch_result["content"]

                                if rss_entries:
                                    new_count = 0
                                    for entry in rss_entries:
                                        entry_text = entry.get("text", "")
                                        url = entry.get("link", "")
                                        published_date_str = entry.get("published")

                                        published_date = None
                                        if published_date_str:
                                            try:
                                                published_date = datetime.fromisoformat(published_date_str)
                                            except Exception:
                                                pass

                                        post_id = None
                                        if url and '/t/' in url:
                                            match = re.search(r'/t/(\d+)', url)
                                            if match:
                                                post_id = match.group(1)

                                        if post_id:
                                            existing_result = await db.execute(
                                                select(Message).filter(Message.website_post_id == f"{website.id}-{post_id}")
                                            )
                                        else:
                                            existing_result = await db.execute(
                                                select(Message).filter(Message.text == entry_text)
                                            )
                                        if existing_result.scalars().first():
                                            continue

                                        message = Message(
                                            website_post_id=f"{website.id}-{post_id}" if post_id else f"{website.id}-{hash(entry_text)}",
                                            website_source_id=website.id,
                                            source_type="website",
                                            text=entry_text,
                                            date=published_date,
                                            sender_username=website.name,
                                            analysis_status="pending",
                                        )
                                        db.add(message)
                                        await db.flush()
                                        new_count += 1

                                    if new_count > 0:
                                        website.last_fetch_new_count = new_count
                                        website.last_fetch_at = func.now()
                                        last_website_fetch_time[website_id] = now
                                        await db.commit()

                                        duration = int((datetime.now() - fetch_start).total_seconds())
                                        await record_fetch_outcome(
                                            source_id=website.id,
                                            source_type="website",
                                            new_jobs=new_jobs_count,
                                            new_messages=new_count,
                                            duration_seconds=duration,
                                        )

                                        try:
                                            await analyze_website_posts(db, website)
                                        except Exception:
                                            pass
                                else:
                                    last_website_fetch_time[website_id] = now

                            except Exception as e:
                                fetch_error = e
                                duration = int((datetime.now() - fetch_start).total_seconds())
                                await record_fetch_outcome(
                                    source_id=website.id,
                                    source_type="website",
                                    new_jobs=0,
                                    new_messages=0,
                                    duration_seconds=duration,
                                    error=e,
                                )

                except Exception:
                    pass

        except asyncio.CancelledError:
            break
        except Exception:
            pass

        await asyncio.sleep(sleep_interval_seconds)


@asynccontextmanager
async def lifespan(app):
    from app.tasks.operations import cleanup_stale_operations
    try:
        await cleanup_stale_operations()
    except Exception:
        pass

    try:
        from app.connection import run_migrations
        await run_migrations()
    except Exception:
        pass

    autonomous_orchestrator = None
    try:
        from app.autonomous.orchestrator import AutonomousOrchestrator
        autonomous_orchestrator = AutonomousOrchestrator()
        asyncio.create_task(autonomous_orchestrator.start())
    except Exception as e:
        logger.error(f"Error starting autonomous orchestrator: {e}", exc_info=True)

    try:
        yield
    finally:
        if autonomous_orchestrator:
            try:
                await autonomous_orchestrator.stop()
            except Exception as e:
                logger.error(f"Error stopping autonomous orchestrator: {e}")

        from app.tasks.listener import telegram_listener_running, stop_telegram_listener
        try:
            for account_id in list(telegram_listener_running.keys()):
                if telegram_listener_running.get(account_id, False):
                    try:
                        await stop_telegram_listener(account_id)
                    except Exception as e:
                        logger.error(f"Error stopping listener for account {account_id}: {e}")
        except Exception as e:
            logger.error(f"Error stopping listeners on shutdown: {e}")

        await stop_cron_task()
