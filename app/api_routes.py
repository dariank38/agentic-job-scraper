"""API routes for job scraper."""

from typing import Optional
from fastapi import HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Channel, Job, Developer, Message, AnalysisRun
from app.tasks import fetch_and_store_messages, analyze_messages


def register_api_routes(app):
    """Register all API routes to the FastAPI app."""

    @app.post("/channels")
    async def add_channel(
        username: str = Form(...),
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Add a new channel."""
        try:
            # Normalize username
            username = username.strip()
            if not username.startswith("@"):
                username = f"@{username}"

            # Check if exists
            result = await db.execute(select(Channel).filter(Channel.username == username))
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="Channel already exists")

            channel = Channel(
                username=username,
                name=name,
                description=description,
            )
            db.add(channel)
            await db.commit()
            await db.refresh(channel)

            return {"success": True, "channel": {"id": channel.id, "username": channel.username}}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to add channel: {str(e)}")

    @app.delete("/channels/{channel_id}")
    async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
        """Delete a channel."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            await db.delete(channel)
            await db.commit()

            return {"success": True}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete channel: {str(e)}")

    @app.post("/channels/{channel_id}/toggle")
    async def toggle_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
        """Toggle channel active status."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            channel.is_active = not channel.is_active
            await db.commit()

            return {"success": True, "is_active": channel.is_active}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle channel: {str(e)}")

    @app.post("/api/reanalyze")
    async def reanalyze_messages(db: AsyncSession = Depends(get_db)):
        """Re-analyze messages that were marked for re-analysis."""
        from telegram_processor import analyze_message
        from app.tasks import should_analyze_message
        from datetime import datetime

        try:
            # Get messages that need re-analysis
            result = await db.execute(select(Message).filter(Message.needs_reanalysis == True))
            messages = result.scalars().all()

            if not messages:
                return {"success": True, "reanalyzed": 0, "message": "No messages need re-analysis"}

            reanalyzed_count = 0
            skipped_count = 0

            for message in messages:
                try:
                    if not message.text:
                        continue

                    # Quick keyword pre-filter
                    if not should_analyze_message(message.text):
                        skipped_count += 1
                        message.needs_reanalysis = False
                        await db.commit()
                        continue

                    analysis = await analyze_message(message.text)

                    if analysis is None:
                        continue

                    category = analysis.get("category", "other")
                    confidence = analysis.get("confidence")
                    translated_text = analysis.get("translated_text")

                    # Delete existing records for this message
                    await db.execute(delete(Job).filter(Job.message_id == message.id))
                    await db.execute(delete(Developer).filter(Developer.message_id == message.id))

                    # Create new record based on category
                    if category == "job_posting":
                        job_data = analysis.get("job_posting", {})
                        # Skip on-site jobs
                        is_remote = job_data.get("is_remote")
                        if is_remote is False:
                            print(f"[Reanalyze] Skipping on-site job: {job_data.get('title', 'unknown')}")
                            message.needs_reanalysis = False
                            await db.commit()
                            continue
                        
                        job = Job(
                            message_id=message.id,
                            channel_id=message.channel_id,
                            confidence=confidence,
                            translated_text=translated_text,
                            title=job_data.get("title"),
                            company=job_data.get("company"),
                            company_link=job_data.get("company_link"),
                            location=job_data.get("location"),
                            is_remote=is_remote,
                            role_type=job_data.get("role_type"),
                            skills=job_data.get("skills", []),
                            contact=job_data.get("contact"),
                            contact_type=job_data.get("contact_type"),
                            summary=job_data.get("summary"),
                        )
                        db.add(job)
                    elif category == "personal_info":
                        pi_data = analysis.get("personal_info", {})
                        developer = Developer(
                            message_id=message.id,
                            channel_id=message.channel_id,
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
                    # "other" category - no record created

                    # Clear re-analysis flag
                    message.needs_reanalysis = False
                    await db.commit()  # Commit after each message for real-time visibility
                    reanalyzed_count += 1
                except Exception as e:
                    await db.rollback()
                    print(f"Error reanalyzing message {message.id}: {e}")
                    continue

            return {"success": True, "reanalyzed": reanalyzed_count, "skipped": skipped_count}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Reanalysis failed: {str(e)}")

    @app.post("/search/{channel_id}")
    async def search_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
        """Search a single channel for jobs with progressive window expansion."""
        result = await db.execute(select(Channel).filter(Channel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Create run record
        run = AnalysisRun(
            run_type="single_channel",
            channel_id=channel.id,
            status="running",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            total_new_messages = 0
            total_analyzed = 0
            total_jobs = 0
            total_developers = 0
            days_back_used = 1

            # Progressive window expansion: 1 day -> 2 days -> ... -> 10 days
            for days_back in range(1, 11):
                # Fetch messages
                fetch_result = await fetch_and_store_messages(db, channel, days_back=days_back, run_id=run.id)
                
                if not fetch_result["success"]:
                    run.status = "failed"
                    run.error_message = fetch_result.get("error", "Unknown error")
                    await db.commit()
                    return {"success": False, "error": fetch_result.get("error")}

                new_messages = fetch_result.get("new_stored", 0)
                total_new_messages += new_messages

                # If no new messages at this window, try expanding
                if new_messages == 0:
                    print(f"[Search] No new messages for {channel.username} at {days_back} days, expanding window...")
                    continue

                # Found new messages, analyze them
                from telegram_processor import is_ollama_available
                if await is_ollama_available():
                    analyze_result = await analyze_messages(db, channel, run_id=run.id)
                    total_analyzed += analyze_result.get("analyzed", 0)
                    total_jobs += analyze_result.get("jobs_found", 0)
                    total_developers += analyze_result.get("developers_found", 0)

                # If we found messages, stop expanding
                days_back_used = days_back
                print(f"[Search] Found {new_messages} new messages for {channel.username} at {days_back} days")
                break

            run.status = "completed"
            run.completed_at = __import__("datetime").datetime.utcnow()
            await db.commit()

            return {
                "success": True,
                "run_id": run.id,
                "days_back_used": days_back_used,
                "total_new_messages": total_new_messages,
                "total_analyzed": total_analyzed,
                "total_jobs": total_jobs,
                "total_developers": total_developers,
            }
        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            await db.commit()
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/search-all")
    async def search_all_channels(db: AsyncSession = Depends(get_db)):
        """Search all active channels with progressive window expansion."""
        result = await db.execute(select(Channel).filter(Channel.is_active == True))
        channels = result.scalars().all()

        results = []
        for channel in channels:
            try:
                # Create run record
                run = AnalysisRun(
                    run_type="single_channel",
                    channel_id=channel.id,
                    status="running",
                )
                db.add(run)
                await db.commit()
                await db.refresh(run)

                total_new_messages = 0
                total_analyzed = 0
                total_jobs = 0
                total_developers = 0
                days_back_used = 1

                # Progressive window expansion: 1 day -> 2 days -> ... -> 10 days
                for days_back in range(1, 11):
                    # Fetch messages
                    fetch_result = await fetch_and_store_messages(db, channel, days_back=days_back, run_id=run.id)
                    
                    if not fetch_result["success"]:
                        run.status = "failed"
                        run.error_message = fetch_result.get("error", "Unknown error")
                        await db.commit()
                        results.append({
                            "channel": channel.username,
                            "success": False,
                            "error": fetch_result.get("error"),
                        })
                        break

                    new_messages = fetch_result.get("new_stored", 0)
                    total_new_messages += new_messages

                    # If no new messages at this window, try expanding
                    if new_messages == 0:
                        print(f"[Search] No new messages for {channel.username} at {days_back} days, expanding window...")
                        continue

                    # Found new messages, analyze them
                    from telegram_processor import is_ollama_available
                    if await is_ollama_available():
                        analyze_result = await analyze_messages(db, channel, run_id=run.id)
                        total_analyzed += analyze_result.get("analyzed", 0)
                        total_jobs += analyze_result.get("jobs_found", 0)
                        total_developers += analyze_result.get("developers_found", 0)

                    # If we found messages, stop expanding
                    days_back_used = days_back
                    print(f"[Search] Found {new_messages} new messages for {channel.username} at {days_back} days")
                    break

                run.status = "completed"
                run.completed_at = __import__("datetime").datetime.utcnow()
                await db.commit()

                results.append({
                    "channel": channel.username,
                    "success": True,
                    "days_back_used": days_back_used,
                    "total_new_messages": total_new_messages,
                    "total_analyzed": total_analyzed,
                    "total_jobs": total_jobs,
                    "total_developers": total_developers,
                })
            except Exception as e:
                await db.rollback()
                results.append({
                    "channel": channel.username,
                    "success": False,
                    "error": str(e),
                })

        return {"success": True, "results": results}

    @app.get("/api/channels")
    async def api_channels(db: AsyncSession = Depends(get_db)):
        """Get all channels as JSON."""
        result = await db.execute(select(Channel))
        channels = result.scalars().all()
        return {
            "channels": [
                {
                    "id": c.id,
                    "username": c.username,
                    "name": c.name,
                    "description": c.description,
                    "is_active": c.is_active,
                    "message_count": len(c.messages),
                    "job_count": len(c.jobs),
                }
                for c in channels
            ]
        }

    @app.get("/api/jobs")
    async def api_jobs(
        remote: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get jobs as JSON."""
        query = select(Job).join(Channel).filter(Channel.is_active == True)

        if remote is not None:
            query = query.filter(Job.is_remote == remote)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get jobs with pagination
        jobs_query = query.order_by(Job.analyzed_at.desc()).offset(offset).limit(limit)
        jobs_result = await db.execute(jobs_query)
        jobs = jobs_result.scalars().all()

        return {
            "jobs": [job.to_dict() for job in jobs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/developers")
    async def api_developers(
        looking_for_work: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get developers as JSON."""
        query = select(Developer).join(Channel).filter(Channel.is_active == True)

        if looking_for_work is not None:
            query = query.filter(Developer.looking_for_work == looking_for_work)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get developers with pagination
        developers_query = query.order_by(Developer.analyzed_at.desc()).offset(offset).limit(limit)
        developers_result = await db.execute(developers_query)
        developers = developers_result.scalars().all()

        return {
            "developers": [dev.to_dict() for dev in developers],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/api/jobs/{job_id}/toggle-applied")
    async def toggle_job_applied(job_id: int, db: AsyncSession = Depends(get_db)):
        """Toggle applied status for a job."""
        from datetime import datetime
        
        try:
            result = await db.execute(select(Job).filter(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            job.is_applied = not job.is_applied
            if job.is_applied:
                job.applied_at = datetime.utcnow()
            else:
                job.applied_at = None
            await db.commit()

            return {"success": True, "is_applied": job.is_applied}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle applied status: {str(e)}")

    @app.post("/api/developers/{developer_id}/toggle-contacted")
    async def toggle_developer_contacted(developer_id: int, db: AsyncSession = Depends(get_db)):
        """Toggle contacted status for a developer."""
        from datetime import datetime
        
        try:
            result = await db.execute(select(Developer).filter(Developer.id == developer_id))
            developer = result.scalar_one_or_none()
            if not developer:
                raise HTTPException(status_code=404, detail="Developer not found")

            developer.is_contacted = not developer.is_contacted
            if developer.is_contacted:
                developer.contacted_at = datetime.utcnow()
            else:
                developer.contacted_at = None
            await db.commit()

            return {"success": True, "is_contacted": developer.is_contacted}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle contacted status: {str(e)}")

    @app.get("/api/messages")
    async def api_messages(
        channel_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get messages as JSON."""
        query = select(Message)

        if channel_id:
            query = query.filter(Message.channel_id == channel_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get messages with pagination
        messages_query = query.order_by(Message.date.desc()).offset(offset).limit(limit)
        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()

        return {
            "messages": [msg.to_dict() for msg in messages],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/stats")
    async def api_stats(db: AsyncSession = Depends(get_db)):
        """Get dashboard statistics."""
        from telegram_processor import is_ollama_available
        from datetime import datetime, timedelta
        
        ollama_available = await is_ollama_available()
        
        # Count channels
        total_channels_result = await db.execute(
            select(func.count()).select_from(Channel).filter(Channel.is_active == True)
        )
        total_channels = total_channels_result.scalar()
        
        # Count pending analysis
        pending_result = await db.execute(
            select(Message).outerjoin(Job).outerjoin(Developer).filter(
                (Job.id == None) & (Developer.id == None),
                Message.text != None,
            )
        )
        pending_analysis = len(pending_result.scalars().all())
        
        # Count by type
        job_postings_result = await db.execute(select(func.count()).select_from(Job))
        job_postings = job_postings_result.scalar()
        
        developers_result = await db.execute(select(func.count()).select_from(Developer))
        developers = developers_result.scalar()
        
        # Application stats with time periods
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(weeks=1)
        one_month_ago = now - timedelta(days=30)
        
        # Job applications
        total_applied_jobs_result = await db.execute(
            select(func.count()).select_from(Job).filter(Job.is_applied == True)
        )
        total_applied_jobs = total_applied_jobs_result.scalar()
        
        daily_applied_jobs_result = await db.execute(
            select(func.count()).select_from(Job).filter(
                Job.is_applied == True,
                Job.applied_at >= one_day_ago
            )
        )
        daily_applied_jobs = daily_applied_jobs_result.scalar()
        
        weekly_applied_jobs_result = await db.execute(
            select(func.count()).select_from(Job).filter(
                Job.is_applied == True,
                Job.applied_at >= one_week_ago
            )
        )
        weekly_applied_jobs = weekly_applied_jobs_result.scalar()
        
        monthly_applied_jobs_result = await db.execute(
            select(func.count()).select_from(Job).filter(
                Job.is_applied == True,
                Job.applied_at >= one_month_ago
            )
        )
        monthly_applied_jobs = monthly_applied_jobs_result.scalar()
        
        # Developer contacts
        total_contacted_developers_result = await db.execute(
            select(func.count()).select_from(Developer).filter(Developer.is_contacted == True)
        )
        total_contacted_developers = total_contacted_developers_result.scalar()
        
        daily_contacted_developers_result = await db.execute(
            select(func.count()).select_from(Developer).filter(
                Developer.is_contacted == True,
                Developer.contacted_at >= one_day_ago
            )
        )
        daily_contacted_developers = daily_contacted_developers_result.scalar()
        
        weekly_contacted_developers_result = await db.execute(
            select(func.count()).select_from(Developer).filter(
                Developer.is_contacted == True,
                Developer.contacted_at >= one_week_ago
            )
        )
        weekly_contacted_developers = weekly_contacted_developers_result.scalar()
        
        monthly_contacted_developers_result = await db.execute(
            select(func.count()).select_from(Developer).filter(
                Developer.is_contacted == True,
                Developer.contacted_at >= one_month_ago
            )
        )
        monthly_contacted_developers = monthly_contacted_developers_result.scalar()
        
        return {
            "total_channels": total_channels,
            "job_postings": job_postings,
            "developers": developers,
            "pending_analysis": pending_analysis,
            "applications": {
                "jobs": {
                    "total": total_applied_jobs,
                    "daily": daily_applied_jobs,
                    "weekly": weekly_applied_jobs,
                    "monthly": monthly_applied_jobs,
                },
                "developers": {
                    "total": total_contacted_developers,
                    "daily": daily_contacted_developers,
                    "weekly": weekly_contacted_developers,
                    "monthly": monthly_contacted_developers,
                },
            },
            "ollama_available": ollama_available,
        }

    @app.get("/api/progress")
    async def api_progress(db: AsyncSession = Depends(get_db)):
        """Get current progress information."""
        # Get latest analysis runs
        recent_runs_result = await db.execute(
            select(AnalysisRun).order_by(AnalysisRun.started_at.desc()).limit(5)
        )
        recent_runs = recent_runs_result.scalars().all()
        
        # Get pending analysis count per channel
        channels_result = await db.execute(
            select(Channel).filter(Channel.is_active == True)
        )
        channels = channels_result.scalars().all()
        
        pending_by_channel = []
        for channel in channels:
            pending_result = await db.execute(
                select(Message).outerjoin(Job).outerjoin(Developer).filter(
                    Message.channel_id == channel.id,
                    (Job.id == None) & (Developer.id == None),
                    Message.text != None,
                )
            )
            pending_count = len(pending_result.scalars().all())
            if pending_count > 0:
                pending_by_channel.append({
                    "channel": channel.username,
                    "pending": pending_count,
                })
        
        return {
            "recent_runs": [
                {
                    "id": run.id,
                    "channel_id": run.channel_id,
                    "status": run.status,
                    "messages_fetched": run.messages_fetched,
                    "messages_analyzed": run.messages_analyzed,
                    "jobs_found": run.jobs_found,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                for run in recent_runs
            ],
            "pending_by_channel": pending_by_channel,
        }
