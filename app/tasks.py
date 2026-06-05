"""Background tasks and helper functions for job scraping."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from telegram_processor import TelegramClientManager, fetch_messages, analyze_message, is_ollama_available
from app.models import Channel, Message, Job, Developer, AnalysisRun
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
        error_msg = str(e).lower()
        # Check if error indicates invalid/non-existent channel
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
            print(f"[Tasks] Channel {channel.username} is invalid/non-existent, removing from DB")
            db.delete(channel)
            db.commit()
            return {
                "success": False,
                "error": f"Channel removed: {str(e)}",
                "channel_removed": True,
            }
        
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        try:
            await manager.disconnect()
        except Exception:
            pass


def should_analyze_message(text: str) -> bool:
    """Quick keyword pre-filter to avoid sending irrelevant messages to Ollama.

    Strategy:
    - If message contains ANY dev-related keyword (inclusion) → send to Ollama
      (even if it also contains non-dev content - Ollama decides)
    - If NO dev keywords but contains clear spam/exclusion keywords → skip
    - If uncertain → send to Ollama anyway
    """
    text_lower = text.lower()

    # Positive keywords - if ANY found, pass to Ollama (handles mixed content)
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
        # Chinese - development roles
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

    # Check inclusion first - if any dev keyword found, send to Ollama
    # This handles mixed content (e.g. marketing message with developer job)
    for keyword in inclusion_keywords:
        if keyword in text_lower:
            return True

    # Negative keywords - only skip if NO dev keywords found at all
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
        "人事", "招聘专员", "教师", "家教",
        "文案", "美工", "平面设计",
        "社群运营", "新媒体运营",
        "房产", "地产", "建筑", "司机", "外卖",
    ]

    # Only skip if purely non-dev content
    for keyword in exclusion_keywords:
        if keyword in text_lower:
            return False

    # Uncertain - let Ollama decide
    return True


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

    # Get unanalyzed messages (no Job or Developer record)
    messages = db.query(Message).filter(
        Message.channel_id == channel.id,
    ).outerjoin(Job).outerjoin(Developer).filter(
        (Job.id == None) & (Developer.id == None),
    ).all()

    analyzed_count = 0
    jobs_found = 0
    developers_found = 0
    skipped_count = 0

    for message in messages:
        if not message.text:
            continue

        # Quick keyword pre-filter
        if not should_analyze_message(message.text):
            skipped_count += 1
            continue

        analysis = await analyze_message(message.text)

        if analysis is None:
            continue

        category = analysis.get("category", "other")
        confidence = analysis.get("confidence")
        translated_text = analysis.get("translated_text")

        # Save to appropriate table based on category
        if category == "job_posting":
            job_data = analysis.get("job_posting", {})
            job = Job(
                message_id=message.id,
                channel_id=channel.id,
                confidence=confidence,
                translated_text=translated_text,
                title=job_data.get("title"),
                company=job_data.get("company"),
                company_link=job_data.get("company_link"),
                location=job_data.get("location"),
                is_remote=job_data.get("is_remote"),
                role_type=job_data.get("role_type"),
                skills=job_data.get("skills", []),
                contact=job_data.get("contact"),
                contact_type=job_data.get("contact_type"),
                summary=job_data.get("summary"),
            )
            db.add(job)
            jobs_found += 1
        elif category == "personal_info":
            pi_data = analysis.get("personal_info", {})
            developer = Developer(
                message_id=message.id,
                channel_id=channel.id,
                confidence=confidence,
                translated_text=translated_text,
                name=pi_data.get("name"),
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
            developers_found += 1
        # "other" category is skipped - no record created

        db.commit()  # Commit after each message for real-time visibility
        analyzed_count += 1

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
        "developers_found": developers_found,
        "skipped": skipped_count,
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
                pending_analysis = db.query(Message).outerjoin(Job).outerjoin(Developer).filter(
                    (Job.id == None) & (Developer.id == None),
                    Message.text != None,
                ).count()

                if ollama_available and pending_analysis > 0:
                    # Prioritize analysis over fetching
                    print(f"[Cron] {pending_analysis} messages pending analysis, running analyze pass...")
                    for channel in channels:
                        try:
                            result = await analyze_messages(db, channel)
                            analyzed = result.get("analyzed", 0)
                            skipped = result.get("skipped", 0)
                            if analyzed > 0 or skipped > 0:
                                print(f"[Cron] {channel.username}: analyzed {analyzed}, skipped {skipped}, jobs {result.get('jobs_found', 0)}, devs {result.get('developers_found', 0)}")
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
