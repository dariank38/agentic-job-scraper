"""Action-related API routes (fetch, analyze, search)."""

from datetime import datetime
from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db
from app.models import AnalysisRun, Channel
from app.tasks import analyze_messages, fetch_and_store_messages


def register_action_routes(app):
    """Register action-related routes."""

    @app.post("/api/fetch/{channel_id}")
    async def fetch_channel(channel_id: int, account_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
        """Fetch messages from a Telegram channel."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            # Use default 10 days back
            from telegram_processor.config import DEFAULT_DAYS_BACK
            days_back = DEFAULT_DAYS_BACK

            result = await fetch_and_store_messages(
                db,
                channel,
                days_back=days_back,
                account_id=account_id
            )

            return {
                "success": result.get("success", True),
                "new_messages": result.get("new_stored", 0),
                "days_back_used": days_back
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")

    @app.post("/api/analyze/{channel_id}")
    async def analyze_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
        """Analyze messages in a channel."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            result = await analyze_messages(
                db,
                channel
            )

            return {
                "success": result.get("success", True),
                "analyzed": result.get("analyzed", 0),
                "jobs_found": result.get("jobs_found", 0),
                "developers_found": result.get("developers_found", 0)
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")

    @app.post("/api/fetch-analyze/{channel_id}")
    async def fetch_analyze_channel(channel_id: int, account_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
        """Fetch and analyze messages in one operation."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            from telegram_processor.config import DEFAULT_DAYS_BACK
            days_back = DEFAULT_DAYS_BACK

            # Fetch
            fetch_result = await fetch_and_store_messages(
                db,
                channel,
                days_back=days_back,
                account_id=account_id
            )

            # Analyze
            analyze_result = await analyze_messages(
                db,
                channel
            )

            return {
                "success": True,
                "total_new_messages": fetch_result.get("new_stored", 0),
                "total_jobs": analyze_result.get("jobs_found", 0),
                "days_back_used": days_back
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to search: {str(e)}")

    @app.post("/api/fetch-all")
    async def fetch_all(db: AsyncSession = Depends(get_db)):
        """Fetch messages from all active channels."""
        try:
            result = await db.execute(select(Channel).filter(Channel.is_active == True))
            channels = result.scalars().all()

            from telegram_processor.config import DEFAULT_DAYS_BACK
            days_back = DEFAULT_DAYS_BACK

            results = []
            for channel in channels:
                try:
                    fetch_result = await fetch_and_store_messages(
                        db,
                        channel,
                        days_back=days_back
                    )
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "new_messages": fetch_result.get("new_stored", 0)
                    })
                except Exception as e:
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "error": str(e)
                    })

            return {"success": True, "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch all: {str(e)}")

    @app.post("/api/analyze-all")
    async def analyze_all(db: AsyncSession = Depends(get_db)):
        """Analyze messages in all active channels."""
        try:
            result = await db.execute(select(Channel).filter(Channel.is_active == True))
            channels = result.scalars().all()

            if not channels:
                return {"success": True, "results": [], "message": "No active channels found"}

            results = []
            for channel in channels:
                try:
                    analyze_result = await analyze_messages(
                        db,
                        channel
                    )
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "analyzed": analyze_result.get("analyzed", 0),
                        "jobs_found": analyze_result.get("jobs_found", 0),
                        "developers_found": analyze_result.get("developers_found", 0),
                        "stopped": analyze_result.get("stopped", False),
                        "remaining": analyze_result.get("remaining", 0)
                    })
                except Exception as e:
                    import traceback
                    error_detail = f"{str(e)}\n{traceback.format_exc()}"
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "error": str(e)
                    })

            return {"success": True, "results": results}
        except Exception as e:
            import traceback
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            raise HTTPException(status_code=500, detail=f"Failed to analyze all: {error_detail}")

    @app.post("/api/fetch-analyze-all")
    async def fetch_analyze_all(db: AsyncSession = Depends(get_db)):
        """Fetch and analyze messages from all active channels."""
        try:
            result = await db.execute(select(Channel).filter(Channel.is_active == True))
            channels = result.scalars().all()

            from telegram_processor.config import DEFAULT_DAYS_BACK
            days_back = DEFAULT_DAYS_BACK

            results = []
            for channel in channels:
                try:
                    fetch_result = await fetch_and_store_messages(
                        db,
                        channel,
                        days_back=days_back
                    )
                    analyze_result = await analyze_messages(
                        db,
                        channel
                    )
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "total_new_messages": fetch_result.get("new_stored", 0),
                        "total_jobs": analyze_result.get("jobs_found", 0)
                    })
                except Exception as e:
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "error": str(e)
                    })

            return {"success": True, "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to search all: {str(e)}")

    @app.post("/api/reanalyze")
    async def reanalyze_messages(db: AsyncSession = Depends(get_db)):
        """Re-analyze messages marked for re-analysis."""
        try:
            from app.models import Message

            result = await db.execute(
                select(Message).filter(Message.needs_reanalysis == True)
            )
            messages = result.scalars().all()

            reanalyzed = 0
            for message in messages:
                try:
                    # BUG FIX: Fetch channel from database since channel variable was undefined
                    channel_result = await db.execute(select(Channel).filter(Channel.id == message.channel_id))
                    channel = channel_result.scalar_one_or_none()

                    from services.ollama_service import get_analyzer
                    analyzer = get_analyzer()
                    analysis = await analyzer.analyze_message(message.text)

                    if analysis.get("category") == "job_posting":
                        from app.models import Job
                        job_data = analysis.get("job_posting", {})
                        job_result = await db.execute(select(Job).filter(Job.message_id == message.id))
                        job = job_result.scalar_one_or_none()

                        if job:
                            job.title = job_data.get("title")
                            job.company = job_data.get("company")
                            job.location = job_data.get("location")
                            job.is_remote = job_data.get("is_remote")
                            job.role_type = job_data.get("role_type")
                            job.skills = job_data.get("skills", [])
                            job.contact = job_data.get("contact")
                            job.summary = job_data.get("summary")
                            job.translated_text = analysis.get("translated_text")
                            job.confidence = analysis.get("confidence")
                            job.analyzed_at = datetime.utcnow()
                            job.needs_reanalysis = False
                        else:
                            new_job = Job(
                                message_id=message.id,
                                channel_id=message.channel_id,
                                channel_name=channel.name if channel else None,  # channel is now defined
                                title=job_data.get("title"),
                                company=job_data.get("company"),
                                location=job_data.get("location"),
                                is_remote=job_data.get("is_remote"),
                                role_type=job_data.get("role_type"),
                                skills=job_data.get("skills", []),
                                contact=job_data.get("contact"),
                                summary=job_data.get("summary"),
                                translated_text=analysis.get("translated_text"),
                                confidence=analysis.get("confidence"),
                            )
                            db.add(new_job)
                            message.needs_reanalysis = False

                    elif analysis.get("category") == "personal_info":
                        from app.models import Developer
                        dev_data = analysis.get("personal_info", {})
                        dev_result = await db.execute(select(Developer).filter(Developer.message_id == message.id))
                        dev = dev_result.scalar_one_or_none()

                        if dev:
                            dev.name = dev_data.get("name")
                            dev.skills = dev_data.get("skills", [])
                            dev.experience = dev_data.get("experience")
                            dev.contact = dev_data.get("contact")
                            dev.looking_for_work = dev_data.get("looking_for_work")
                            dev.summary = dev_data.get("summary")
                            dev.translated_text = analysis.get("translated_text")
                            dev.confidence = analysis.get("confidence")
                            dev.analyzed_at = datetime.utcnow()
                            message.needs_reanalysis = False
                        else:
                            new_dev = Developer(
                                message_id=message.id,
                                channel_id=message.channel_id,
                                name=dev_data.get("name"),
                                skills=dev_data.get("skills", []),
                                experience=dev_data.get("experience"),
                                contact=dev_data.get("contact"),
                                looking_for_work=dev_data.get("looking_for_work"),
                                summary=dev_data.get("summary"),
                                translated_text=analysis.get("translated_text"),
                                confidence=analysis.get("confidence"),
                            )
                            db.add(new_dev)
                            message.needs_reanalysis = False

                    else:
                        message.needs_reanalysis = False

                    reanalyzed += 1
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    continue

            return {"success": True, "reanalyzed": reanalyzed}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reanalyze: {str(e)}")

    @app.post("/api/reanalyze-skipped")
    async def reanalyze_skipped_messages(db: AsyncSession = Depends(get_db)):
        """Re-analyze all messages that were skipped."""
        try:
            from app.models import Message
            from app.tasks import analyze_messages

            # Find all skipped messages
            result = await db.execute(
                select(Message).filter(Message.analysis_status == "skipped")
            )
            skipped_messages = result.scalars().all()

            if not skipped_messages:
                return {"success": True, "message": "No skipped messages to re-analyze"}

            # Reset status to pending
            for msg in skipped_messages:
                msg.analysis_status = "pending"
            await db.commit()

            # Analyze all channels that have skipped messages
            channel_ids = set(msg.channel_id for msg in skipped_messages)
            results = []

            for channel_id in channel_ids:
                channel_result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                channel = channel_result.scalar_one_or_none()
                if channel:
                    result = await analyze_messages(db, channel)
                    results.append({
                        "channel_id": channel_id,
                        "channel_username": channel.username,
                        "result": result
                    })

            return {"success": True, "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to re-analyze skipped messages: {str(e)}")

    @app.post("/api/reanalyze-message/{message_id}")
    async def reanalyze_single_message(message_id: int, db: AsyncSession = Depends(get_db)):
        """Re-analyze a single skipped message."""
        try:
            from app.models import Message, Job, Developer
            from app.tasks import _analyze_single
            from services.ollama_service import get_analyzer, is_ollama_available

            if not await is_ollama_available():
                raise HTTPException(status_code=500, detail="Ollama not available")

            result = await db.execute(select(Message).filter(Message.id == message_id))
            message = result.scalar_one_or_none()
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            # Fetch channel for channel_name reference
            from app.models import Channel
            channel_result = await db.execute(select(Channel).filter(Channel.id == message.channel_id))
            channel = channel_result.scalar_one_or_none()

            # Reset status to pending
            message.analysis_status = "pending"
            await db.commit()

            # Analyze the message
            analyzer = get_analyzer()
            message, result, error = await _analyze_single(analyzer, message)

            if error:
                message.analysis_status = "skipped"
                await db.commit()
                raise HTTPException(status_code=500, detail=f"Analysis failed: {str(error)}")

            if not result or result.get("category") == "other":
                message.analysis_status = "skipped"
                await db.commit()
                return {"success": True, "analyzed": False, "reason": "No relevant content found"}

            # Process the result
            category = result.get("category", "other")
            confidence = result.get("confidence")
            translated_text = result.get("translated_text")

            if category == "job_posting" and result.get("job_posting"):
                job_data = result.get("job_posting", {})
                is_remote = job_data.get("is_remote")
                if is_remote is False:
                    message.analysis_status = "skipped"
                    await db.commit()
                    return {"success": True, "analyzed": False, "reason": "On-site job filtered"}

                location = job_data.get("location")
                if isinstance(location, list):
                    location = ", ".join(location)

                contact = job_data.get("contact")
                if isinstance(contact, list):
                    contact = ", ".join(contact)

                contact_type = job_data.get("contact_type")
                if isinstance(contact_type, list):
                    contact_type = ", ".join(contact_type)

                role_type = job_data.get("role_type")
                if isinstance(role_type, list):
                    role_type = ", ".join(role_type)

                title = job_data.get("title")
                company = job_data.get("company")
                if title and company:
                    existing_job_result = await db.execute(
                        select(Job).filter(
                            Job.title == title,
                            Job.company == company,
                        )
                    )
                    existing_job = existing_job_result.scalar_one_or_none()
                    if existing_job:
                        message.analysis_status = "skipped"
                        await db.commit()
                        return {"success": True, "analyzed": False, "reason": "Duplicate job"}

                from app.models import Job
                job = Job(
                    message_id=message.id,
                    channel_id=message.channel_id,
                    channel_name=channel.name if channel else None,
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
                message.analysis_status = "analyzed"
                await db.commit()
                return {"success": True, "analyzed": True, "type": "job"}

            elif category == "personal_info" and result.get("personal_info"):
                pi_data = result.get("personal_info", {})

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

                name = pi_data.get("name")
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
                        existing_dev = existing_dev_result.scalar_one_or_none()
                        if existing_dev:
                            message.analysis_status = "skipped"
                            await db.commit()
                            return {"success": True, "analyzed": False, "reason": "Duplicate developer"}

                developer = Developer(
                    message_id=message.id,
                    channel_id=message.channel_id,
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
                message.analysis_status = "analyzed"
                await db.commit()
                return {"success": True, "analyzed": True, "type": "developer"}
            else:
                message.analysis_status = "skipped"
                await db.commit()
                return {"success": True, "analyzed": False, "reason": "No relevant category"}

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to re-analyze message: {str(e)}")

    @app.post("/api/stop-analyze")
    # BUG FIX: Add channel_id parameter to match stop_analysis(channel_id) signature in tasks.py
    async def stop_analyze(channel_id: int):
        """Stop the current analysis process for a specific channel."""
        try:
            from app.tasks import stop_analysis
            stop_analysis(channel_id)
            return {"success": True, "message": "Stop signal sent"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop analysis: {str(e)}")

    @app.post("/api/cron/start")
    async def start_cron():
        """Start the continuous scanner cron job."""
        try:
            from app.tasks import start_cron_task
            started = start_cron_task()
            if started:
                return {"success": True, "message": "Cron job started"}
            else:
                return {"success": False, "message": "Cron job is already running"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start cron: {str(e)}")

    @app.post("/api/cron/stop")
    async def stop_cron():
        """Stop the continuous scanner cron job."""
        try:
            from app.tasks import stop_cron_task
            stopped = stop_cron_task()
            if stopped:
                return {"success": True, "message": "Cron job stopped"}
            else:
                return {"success": False, "message": "Cron job is not running"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop cron: {str(e)}")

    @app.get("/api/cron/status")
    async def cron_status():
        """Get the current status of the cron job."""
        try:
            from app.tasks import is_cron_running
            running = is_cron_running()
            return {"success": True, "running": running}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get cron status: {str(e)}")

    @app.get("/api/telegram-dialogs")
    async def get_telegram_dialogs(account_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
        """Get available Telegram dialogs (channels/groups), excluding those already in database."""
        try:
            import asyncio
            from telegram_processor import TelegramClientManager, get_dialogs
            from app.models import TelegramAccount

            # Get Telegram account from database
            if account_id:
                result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
                account = result.scalar_one_or_none()
                if not account:
                    raise HTTPException(status_code=404, detail="Telegram account not found")
            else:
                # Get first active account
                result = await db.execute(
                    select(TelegramAccount).filter(TelegramAccount.is_active == True, TelegramAccount.is_authenticated == True)
                )
                account = result.scalars().first()
                if not account:
                    raise HTTPException(
                        status_code=400,
                        detail="No active authenticated Telegram account found. Please add a Telegram account in Settings > Telegram Accounts and authenticate it first."
                    )

            # Get existing channel usernames from database
            result = await db.execute(select(Channel.username))
            existing_usernames = set(row[0].lower() for row in result.all() if row[0])

            # Create Telegram client with account credentials
            telegram_manager = TelegramClientManager(
                api_id=account.api_id,
                api_hash=account.api_hash,
                phone_number=account.phone_number,
                session_name=account.session_name,
            )

            await telegram_manager.connect()
            try:
                dialogs = await get_dialogs(telegram_manager.client)
            finally:
                await telegram_manager.disconnect()

            # Filter out existing channels
            filtered_dialogs = []
            for dialog in dialogs:
                username = (dialog.get('username') or '').lower()
                username_with_at = username if username.startswith('@') else f'@{username}'
                if username and (username not in existing_usernames and username_with_at not in existing_usernames):
                    filtered_dialogs.append(dialog)

            return {"success": True, "dialogs": filtered_dialogs}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get dialogs: {str(e)}")