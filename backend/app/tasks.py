"""Background tasks and helper functions for job scraping."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal, get_db, manager
from app.models import AnalysisRun, Channel, Developer, Job, Message, Operation, TelegramAccount
from telegram_processor import TelegramClientManager, fetch_messages
from services.ollama_service import get_analyzer, is_ollama_available

logger = logging.getLogger(__name__)

# Global stop events for cancelling analysis (per-channel)
analysis_stop_events: dict[int, asyncio.Event] = {}

# Cron job state
cron_running = False
cron_task: asyncio.Task | None = None


def reset_stop_event(channel_id: int):
    """Reset stop event for a channel before starting analysis."""
    # Clean up old events first to prevent memory leak
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


def cleanup_old_stop_events(max_age_seconds: int = 3600):
    """Remove old stop events to prevent memory leak."""
    # This is a safety measure - in practice, events should be cleaned up
    # immediately after analysis completes via cleanup_stop_event()
    pass


def is_cron_running() -> bool:
    return cron_running


def start_cron_task() -> bool:
    global cron_running, cron_task
    if cron_running:
        return False
    cron_running = True
    cron_task = asyncio.create_task(continuous_scanner())
    return True


def stop_cron_task() -> bool:
    global cron_running, cron_task
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
    except Exception as e:
        pass


async def create_operation(
    db: AsyncSession,
    operation_type: str,
    channel: Channel,
) -> int:
    from app.models import Operation
    operation = Operation(
        operation_type=operation_type,
        channel_id=channel.id,
        channel_username=channel.username,
        status="running",
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
    analyzed: Optional[int] = None,
    jobs_found: Optional[int] = None,
    developers_found: Optional[int] = None,
    error_message: Optional[str] = None,
    commit: bool = True,
):
    """Update operation progress. Use commit=False to batch updates."""
    from app.models import Operation
    result = await db.execute(select(Operation).filter(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if operation:
        if status is not None:
            operation.status = status
        if current is not None:
            operation.current = current
        if total is not None:
            operation.total = total
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


# ── PRE-FILTER ────────────────────────────────────────────────────────────────
# DISABLED: Pre-filtering disabled to analyze all messages with Ollama

# def should_analyze_message(text: str) -> bool:
#     text_lower = text.lower()
#
#     exclusion_keywords = [
#         "marketing", "seo", "digital marketing", "growth hacker",
#         "advertising", "dropshipping", "mlm",
#         "crypto investment", "forex", "trading signal",
#         "airdrop", "casino", "gambling", "betting",
#         "medical", "healthcare", "nursing", "doctor", "pharmacist",
#         "accountant", "accounting", "finance manager", "auditor",
#         "graphic designer", "visual designer",
#         "content writer", "copywriter", "journalist",
#         "community manager", "social media manager",
#         "community moderator",
#         "real estate", "property agent", "construction worker",
#         "driver", "delivery rider", "cleaning",
#         "customer service", "customer support", "call center",
#         "recruiter", "talent acquisition", "headhunter",
#         "hr manager", "human resources",
#         "product manager", "project manager",
#         "teacher", "tutor", "professor",
#         # Chinese
#         "营销", "推广", "广告", "销售", "微商",
#         "投资", "外汇", "赌博", "博彩",
#         "医疗", "护士", "医生", "会计", "财务",
#         "人力资源", "人事", "招聘专员", "猎头",
#         "社群运营", "新媒体运营", "内容运营", "运营专员", "运营经理",
#         "文案", "编辑", "平面设计", "客服",
#         "产品经理", "项目经理", "商务",
#         "房产", "建筑工", "司机", "快递员",
#         "ui设计", "ux设计", "视觉设计",
#     ]
#
#     for keyword in exclusion_keywords:
#         if keyword in text_lower:
#             return False
#
#     role_keywords = [
#         "software engineer", "software developer", "software programmer",
#         "backend", "frontend", "front-end", "front end",
#         "fullstack", "full-stack", "full stack",
#         "devops", "platform engineer", "site reliability", "sre",
#         "mobile developer", "ios developer", "android developer",
#         "ml engineer", "ai engineer", "data engineer", "data scientist",
#         "blockchain developer", "smart contract", "web3 developer",
#         "qa engineer", "test engineer", "automation engineer",
#         "security engineer", "cloud engineer", "infrastructure engineer",
#         "tech lead", "team lead", "staff engineer", "principal engineer",
#         "solutions architect", "software architect", "cto",
#         "junior developer", "senior developer", "junior engineer", "senior engineer",
#         "web developer", "programmer", "coder",
#         # Chinese roots
#         "前端", "后端", "全栈", "运维",
#         "移动开发", "安卓", "鸿蒙",
#         "区块链", "智能合约",
#         "数据工程", "算法", "机器学习", "人工智能", "大模型",
#         "爬虫", "研发", "架构师", "技术负责人", "小程序",
#         "测试工程",
#     ]
#
#     stack_keywords = [
#         "python", "javascript", "typescript",
#         "golang", "rust", "java", "kotlin", "swift", "scala", "elixir",
#         "php", "ruby", "c++", "c#",
#         "react", "vue", "angular", "next.js", "nuxt", "svelte",
#         "h5", "uni-app", "uniapp", "taro",
#         "antd", "ant design", "element ui", "element plus",
#         "webpack", "vite",
#         "django", "flask", "fastapi", "laravel", "rails",
#         "spring boot", "springboot", "spring cloud", "mybatis", "dubbo",
#         "node.js", "nodejs", "express", "nestjs",
#         "flutter", "react native",
#         "docker", "kubernetes", "k8s", "terraform", "jenkins",
#         "ci/cd", "cicd", "github actions",
#         "aws", "gcp", "azure", "阿里云", "腾讯云", "华为云",
#         "linux",
#         "postgresql", "mongodb", "redis", "mysql", "elasticsearch",
#         "flink", "spark", "hadoop", "kafka",
#         "graphql", "microservices",
#         "分布式", "高并发", "中间件",
#         "solidity", "web3.js", "ethers.js",
#         "llm", "rag", "langchain",
#     ]
#
#     has_role = any(kw in text_lower for kw in role_keywords)
#     has_stack = any(kw in text_lower for kw in stack_keywords)
#
#     # role or stack keywords indicate software development content
#     return has_role or has_stack


# ── FETCH ─────────────────────────────────────────────────────────────────────

async def fetch_and_store_messages(
    db: AsyncSession,
    channel: Channel,
    days_back: int = 10,
    run_id: Optional[int] = None,
    account_id: Optional[int] = None,
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

    operation_id = await create_operation(db, "fetch", channel)

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
                        "new": new_count,
                        "operation_id": operation_id,
                    })
                    await update_operation(db, operation_id, current=i + 1, total=len(messages))

            except Exception as e:
                continue

        await db.commit()

        channel.last_fetch_new_count = new_count
        channel.last_fetch_at = datetime.utcnow()
        await db.commit()

        await broadcast_progress("fetch_complete", {"channel": channel.username, "new_messages": new_count, "operation_id": operation_id})
        await update_operation(db, operation_id, status="completed")

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
            except Exception as delete_error:
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
) -> dict:
    """Analyze unanalyzed messages with AI using concurrent pipeline."""
    if not await is_ollama_available():
        return {"success": False, "error": "Ollama not available"}

    operation_id = await create_operation(db, "analyze", channel)

    try:
        reset_stop_event(channel.id)
        await broadcast_progress("analyze_start", {"channel": channel.username, "channel_id": channel.id, "operation_id": operation_id})

        # BUG FIX: Add analysis_status == "pending" filter to avoid re-analyzing skipped messages
        messages_result = await db.execute(
            select(Message).filter(
                Message.channel_id == channel.id,
                Message.analysis_status == "pending",
            ).outerjoin(Job).outerjoin(Developer).filter(
                (Job.id == None) & (Developer.id == None),
            )
        )
        messages = messages_result.scalars().all()
        await broadcast_progress("analyze_progress", {"channel": channel.username, "status": "found", "total": len(messages), "operation_id": operation_id})
        await update_operation(db, operation_id, total=len(messages))

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

        # Token usage tracking
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        logger.info(f"Analyzing {total_messages} messages in {total_batches} batches of {batch_size} with stop support")

        for batch_num, batch_start in enumerate(range(0, total_messages, batch_size), 1):
            if is_analysis_stopped(channel.id):
                stopped_count = total_messages - batch_start
                break

            batch = messages[batch_start:batch_start + batch_size]

            filtered_messages = []
            for msg in batch:
                # Pre-filtering disabled - analyze all messages with Ollama
                if msg.text:  # and should_analyze_message(msg.text):
                    filtered_messages.append(msg)
                else:
                    skipped_count += 1
                    msg.analysis_status = "skipped"

            if not filtered_messages:
                await broadcast_progress("analyze_progress", {"channel": channel.username, "current": batch_num, "total": total_batches, "operation_id": operation_id})
                await update_operation(db, operation_id, current=batch_num)
                continue

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

                # Track token usage from this message
                usage = result.get("usage", {})
                msg_input_tokens = usage.get("input_tokens", 0)
                msg_output_tokens = usage.get("output_tokens", 0)
                msg_total_tokens = usage.get("total_tokens", 0)

                total_input_tokens += msg_input_tokens
                total_output_tokens += msg_output_tokens
                total_tokens += msg_total_tokens

                category = result.get("category")
                confidence = result.get("confidence")
                translated_text = result.get("translated_text")

                # ── JOB POSTING ───────────────────────────────────────────────
                if category == "job_posting":
                    job_data = result.get("job_posting") or {}

                    is_remote = job_data.get("is_remote")
                    if is_remote is False:
                        skipped_count += 1
                        message.analysis_status = "skipped"
                        continue

                    title = job_data.get("title")
                    company = job_data.get("company")

                    location = job_data.get("location")
                    if isinstance(location, list):
                        location = ", ".join(location)

                    contact = job_data.get("contact")
                    if isinstance(contact, list):
                        contact = ", ".join(contact)

                    contact_type = job_data.get("contact_type")
                    if isinstance(contact_type, list):
                        contact_type = ", ".join(contact_type)

                    if not contact:
                        contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
                        contact_type = "telegram" if contact else None

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
                        channel_id=channel.id,
                        channel_name=channel.name,
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

                    contact = pi_data.get("contact")
                    if isinstance(contact, list):
                        contact = ", ".join(contact)

                    contact_type = pi_data.get("contact_type")
                    if isinstance(contact_type, list):
                        contact_type = ", ".join(contact_type)

                    portfolio = pi_data.get("portfolio")
                    if isinstance(portfolio, list):
                        portfolio = ", ".join(portfolio)

                    github = pi_data.get("github")
                    if isinstance(github, list):
                        github = ", ".join(github)

                    linkedin = pi_data.get("linkedin")
                    if isinstance(linkedin, list):
                        linkedin = ", ".join(linkedin)

                    if not contact:
                        contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
                        contact_type = "telegram" if contact else None

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
                        channel_id=channel.id,
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

            await broadcast_progress("analyze_progress", {
                "channel": channel.username,
                "channel_id": channel.id,
                "current": batch_num,
                "total": total_batches,
                "analyzed": analyzed_count,
                "jobs": jobs_added,
                "developers": devs_added,
                "operation_id": operation_id,
                "tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_tokens,
                }
            })
            await update_operation(db, operation_id, current=batch_num, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)

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
        status = "stopped" if stopped_count > 0 else "completed"
        await broadcast_progress("analyze_complete", {
            "channel": channel.username,
            "channel_id": channel.id,
            "analyzed": analyzed_count,
            "jobs": jobs_added,
            "developers": devs_added,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
            "operation_id": operation_id,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_tokens,
            }
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
        # Clean up stop event to prevent memory leak
        cleanup_stop_event(channel.id)


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

                    now = datetime.now()
                    last = last_fetch_time.get(channel.id)
                    due = last is None or (now - last).total_seconds() >= fetch_interval_minutes * 60

                    if due:
                        try:
                            fetch_result = await fetch_and_store_messages(db, channel, days_back=1)
                            if fetch_result["success"]:
                                last_fetch_time[channel.id] = now

                                if fetch_result["new_stored"] > 0:
                                    try:
                                        analyze_result = await analyze_messages(db, channel)
                                    except Exception as e:
                                        pass
                        except Exception as e:
                            pass
                    else:
                        mins_left = int((fetch_interval_minutes * 60 - (now - last).total_seconds()) / 60)
                        pass

                except Exception as e:
                    pass

        except asyncio.CancelledError:
            break
        except Exception as e:
            pass

        await asyncio.sleep(sleep_interval_seconds)


# ── LIFESPAN ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown events."""
    # Cron job no longer starts automatically - must be started manually via API
    try:
        yield
    finally:
        stop_cron_task()  # Clean up on app shutdown