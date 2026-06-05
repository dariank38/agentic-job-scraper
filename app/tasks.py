"""Background tasks and helper functions for job scraping."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from telegram_processor import TelegramClientManager, fetch_messages, analyze_message, is_ollama_available
from app.models import Channel, Message, Job, AnalysisRun
from app.connection import get_db


async def fetch_and_store_messages(
    db: Session,
    channel: Channel,
    days_back: int = 10,
    run_id: Optional[int] = None,
) -> dict:
    """Fetch messages from Telegram and store in database."""
    manager = TelegramClientManager()

    try:
        await manager.connect()

        # Fetch messages
        messages = await fetch_messages(
            manager.client,
            channel.username,
            days_back=days_back,
        )

        # Store in database
        new_count = 0
        for msg_data in messages:
            # Check if message already exists
            existing = db.query(Message).filter(
                Message.telegram_id == msg_data["id"],
                Message.channel_id == channel.id,
            ).first()

            if existing:
                continue

            sender = msg_data.get("sender", {})

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
            new_count += 1

        db.commit()

        # Update run stats if provided
        if run_id:
            run = db.query(AnalysisRun).get(run_id)
            if run:
                run.messages_fetched += len(messages)
                db.commit()

        return {
            "success": True,
            "fetched": len(messages),
            "new_stored": new_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        try:
            await manager.disconnect()
        except Exception:
            pass


async def analyze_messages(
    db: Session,
    channel: Channel,
    run_id: Optional[int] = None,
) -> dict:
    """Analyze unanalyzed messages with AI."""
    if not await is_ollama_available():
        return {
            "success": False,
            "error": "Ollama not available",
        }

    # Get unanalyzed messages
    messages = db.query(Message).filter(
        Message.channel_id == channel.id,
    ).outerjoin(Job).filter(
        Job.id == None,
    ).all()

    analyzed_count = 0
    jobs_found = 0

    for message in messages:
        if not message.text:
            continue

        analysis = await analyze_message(message.text)

        if analysis is None:
            continue

        category = analysis.get("category", "other")
        extracted = analysis.get("extracted", {})
        is_remote = extracted.get("remote")

        # Always create a Job record to mark message as analyzed.
        # category="other" means non-tech/onsite — saved but hidden from UI.
        job = Job(
            message_id=message.id,
            channel_id=channel.id,
            category=category,
            confidence=analysis.get("confidence"),
            ai_title=extracted.get("title"),
            ai_company=extracted.get("company"),
            ai_company_link=extracted.get("company_link"),
            ai_location=extracted.get("location"),
            ai_remote=is_remote,
            ai_role_type=extracted.get("role_type"),
            ai_skills=extracted.get("skills", []),
            ai_contact=extracted.get("contact"),
            ai_contact_type=extracted.get("contact_type"),
            ai_summary=extracted.get("summary"),
        )
        db.add(job)
        analyzed_count += 1

        if category in ["job_posting", "remote_work"]:
            jobs_found += 1

    db.commit()

    # Update run stats
    if run_id:
        run = db.query(AnalysisRun).get(run_id)
        if run:
            run.messages_analyzed += analyzed_count
            run.jobs_found += jobs_found
            db.commit()

    return {
        "success": True,
        "analyzed": analyzed_count,
        "jobs_found": jobs_found,
    }


async def continuous_scanner(
    fetch_interval_minutes: int = 30,
    analyze_interval_seconds: int = 30,
) -> None:
    """Continuously scan channels and analyze messages.

    Strategy:
    - If Ollama is busy analyzing queued messages, skip fetching new ones.
    - Fetch channels one at a time in round-robin order.
    - Analyze unprocessed messages continuously between fetches.
    """
    print(f"[Cron] Starting continuous scanner")

    channel_index = 0  # Round-robin pointer
    last_fetch_time: dict[int, datetime] = {}  # channel_id -> last fetch time

    while True:
        try:
            db = get_db()

            try:
                channels = db.query(Channel).filter(Channel.is_active == True).all()

                if not channels:
                    print("[Cron] No active channels configured, waiting...")
                    await asyncio.sleep(analyze_interval_seconds)
                    continue

                ollama_available = await is_ollama_available()

                # Count total unanalyzed messages across all channels
                pending_analysis = db.query(Message).outerjoin(Job).filter(
                    Job.id == None,
                    Message.text != None,
                ).count()

                if ollama_available and pending_analysis > 0:
                    # Prioritize analysis over fetching
                    print(f"[Cron] {pending_analysis} messages pending analysis, running analyze pass...")
                    for channel in channels:
                        try:
                            result = await analyze_messages(db, channel)
                            analyzed = result.get("analyzed", 0)
                            if analyzed > 0:
                                print(f"[Cron] {channel.username}: analyzed {analyzed}, jobs {result.get('jobs_found', 0)}")
                        except Exception as e:
                            print(f"[Cron] {channel.username}: analyze EXCEPTION - {e}")
                else:
                    # No pending analysis — fetch next channel in round-robin
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

            finally:
                db.close()

        except Exception as e:
            print(f"[Cron] CRITICAL ERROR: {e}")

        await asyncio.sleep(analyze_interval_seconds)


@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown events - includes continuous background scanning."""
    from app.connection import init_db

    # Startup
    init_db()

    # Start background cron job for continuous scanning
    cron_task = asyncio.create_task(continuous_scanner())

    yield

    # Shutdown
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass
