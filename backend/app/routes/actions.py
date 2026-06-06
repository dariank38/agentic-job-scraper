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
    async def fetch_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
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
                days_back=days_back
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

    @app.post("/api/search/{channel_id}")
    async def search_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
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
                days_back=days_back
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
                        "jobs_found": analyze_result.get("jobs_found", 0)
                    })
                except Exception as e:
                    results.append({
                        "channel_id": channel.id,
                        "username": channel.username,
                        "error": str(e)
                    })

            return {"success": True, "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to analyze all: {str(e)}")

    @app.post("/api/search-all")
    async def search_all(db: AsyncSession = Depends(get_db)):
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

    @app.post("/api/stop-analyze")
    async def stop_analyze():
        """Stop the current analysis process."""
        try:
            from app.tasks import stop_analysis
            stop_analysis()
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
    async def get_telegram_dialogs():
        """Get available Telegram dialogs (channels/groups)."""
        try:
            from telegram_processor import get_dialogs
            dialogs = await get_dialogs()
            return {"success": True, "dialogs": dialogs}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get dialogs: {str(e)}")
