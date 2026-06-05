"""API routes for job scraper."""

from typing import Optional
from fastapi import HTTPException, Depends, Form
from sqlalchemy.orm import Session

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
        db: Session = Depends(get_db),
    ):
        """Add a new channel."""
        # Normalize username
        username = username.strip()
        if not username.startswith("@"):
            username = f"@{username}"

        # Check if exists
        existing = db.query(Channel).filter(Channel.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Channel already exists")

        channel = Channel(
            username=username,
            name=name,
            description=description,
        )
        db.add(channel)
        db.commit()

        return {"success": True, "channel": {"id": channel.id, "username": channel.username}}

    @app.delete("/channels/{channel_id}")
    async def delete_channel(channel_id: int, db: Session = Depends(get_db)):
        """Delete a channel."""
        channel = db.query(Channel).get(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        db.delete(channel)
        db.commit()

        return {"success": True}

    @app.post("/channels/{channel_id}/toggle")
    async def toggle_channel(channel_id: int, db: Session = Depends(get_db)):
        """Toggle channel active status."""
        channel = db.query(Channel).get(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        channel.is_active = not channel.is_active
        db.commit()

        return {"success": True, "is_active": channel.is_active}

    @app.post("/api/reanalyze")
    async def reanalyze_messages(db: Session = Depends(get_db)):
        """Re-analyze messages that were marked for re-analysis."""
        from telegram_processor import analyze_message
        from app.tasks import should_analyze_message
        from datetime import datetime

        # Get messages that need re-analysis
        messages = db.query(Message).filter(Message.needs_reanalysis == True).all()

        if not messages:
            return {"success": True, "reanalyzed": 0, "message": "No messages need re-analysis"}

        reanalyzed_count = 0
        skipped_count = 0

        for message in messages:
            if not message.text:
                continue

            # Quick keyword pre-filter
            if not should_analyze_message(message.text):
                skipped_count += 1
                message.needs_reanalysis = False
                db.commit()
                continue

            analysis = await analyze_message(message.text)

            if analysis is None:
                continue

            category = analysis.get("category", "other")
            confidence = analysis.get("confidence")
            translated_text = analysis.get("translated_text")

            # Delete existing records for this message
            db.query(Job).filter(Job.message_id == message.id).delete()
            db.query(Developer).filter(Developer.message_id == message.id).delete()

            # Create new record based on category
            if category == "job_posting":
                job_data = analysis.get("job_posting", {})
                job = Job(
                    message_id=message.id,
                    channel_id=message.channel_id,
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
            db.commit()  # Commit after each message for real-time visibility
            reanalyzed_count += 1

        return {"success": True, "reanalyzed": reanalyzed_count, "skipped": skipped_count}

    @app.post("/search/{channel_id}")
    async def search_channel(channel_id: int, db: Session = Depends(get_db)):
        """Search a single channel for jobs."""
        channel = db.query(Channel).get(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Create run record
        run = AnalysisRun(
            run_type="single_channel",
            channel_id=channel.id,
            status="running",
        )
        db.add(run)
        db.commit()

        # Run search
        fetch_result = await fetch_and_store_messages(db, channel, days_back=0, run_id=run.id)

        if not fetch_result["success"]:
            run.status = "failed"
            run.error_message = fetch_result.get("error", "Unknown error")
            db.commit()
            return {"success": False, "error": fetch_result.get("error")}

        # Analyze if Ollama available
        from telegram_processor import is_ollama_available
        if await is_ollama_available():
            analyze_result = await analyze_messages(db, channel, run_id=run.id)
        else:
            analyze_result = {"analyzed": 0, "jobs_found": 0}

        run.status = "completed"
        run.completed_at = __import__("datetime").datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "fetched": fetch_result["fetched"],
            "new_stored": fetch_result["new_stored"],
            "analyzed": analyze_result.get("analyzed", 0),
            "jobs_found": analyze_result.get("jobs_found", 0),
        }

    @app.post("/search-all")
    async def search_all_channels(db: Session = Depends(get_db)):
        """Search all active channels."""
        channels = db.query(Channel).filter(Channel.is_active == True).all()

        results = []
        for channel in channels:
            result = await search_channel(channel.id, db)
            results.append({
                "channel": channel.username,
                "result": result,
            })

        return {"success": True, "results": results}

    @app.get("/api/channels")
    async def api_channels(db: Session = Depends(get_db)):
        """Get all channels as JSON."""
        channels = db.query(Channel).all()
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
        db: Session = Depends(get_db),
    ):
        """Get jobs as JSON."""
        query = db.query(Job).join(Channel).filter(Channel.is_active == True)

        if remote is not None:
            query = query.filter(Job.is_remote == remote)

        total = query.count()
        jobs = query.order_by(Job.analyzed_at.desc()).offset(offset).limit(limit).all()

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
        db: Session = Depends(get_db),
    ):
        """Get developers as JSON."""
        query = db.query(Developer).join(Channel).filter(Channel.is_active == True)

        if looking_for_work is not None:
            query = query.filter(Developer.looking_for_work == looking_for_work)

        total = query.count()
        developers = query.order_by(Developer.analyzed_at.desc()).offset(offset).limit(limit).all()

        return {
            "developers": [dev.to_dict() for dev in developers],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/api/jobs/{job_id}/toggle-applied")
    async def toggle_job_applied(job_id: int, db: Session = Depends(get_db)):
        """Toggle applied status for a job."""
        from datetime import datetime
        
        job = db.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job.is_applied = not job.is_applied
        if job.is_applied:
            job.applied_at = datetime.utcnow()
        else:
            job.applied_at = None
        db.commit()

        return {"success": True, "is_applied": job.is_applied}

    @app.post("/api/developers/{developer_id}/toggle-contacted")
    async def toggle_developer_contacted(developer_id: int, db: Session = Depends(get_db)):
        """Toggle contacted status for a developer."""
        from datetime import datetime
        
        developer = db.query(Developer).get(developer_id)
        if not developer:
            raise HTTPException(status_code=404, detail="Developer not found")

        developer.is_contacted = not developer.is_contacted
        if developer.is_contacted:
            developer.contacted_at = datetime.utcnow()
        else:
            developer.contacted_at = None
        db.commit()

        return {"success": True, "is_contacted": developer.is_contacted}

    @app.get("/api/messages")
    async def api_messages(
        channel_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        db: Session = Depends(get_db),
    ):
        """Get messages as JSON."""
        query = db.query(Message)

        if channel_id:
            query = query.filter(Message.channel_id == channel_id)

        total = query.count()
        messages = query.order_by(Message.date.desc()).offset(offset).limit(limit).all()

        return {
            "messages": [msg.to_dict() for msg in messages],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/stats")
    async def api_stats(db: Session = Depends(get_db)):
        """Get dashboard statistics."""
        from telegram_processor import is_ollama_available
        from datetime import datetime, timedelta
        
        ollama_available = await is_ollama_available()
        
        # Count pending analysis
        pending_analysis = db.query(Message).outerjoin(Job).outerjoin(Developer).filter(
            (Job.id == None) & (Developer.id == None),
            Message.text != None,
        ).count()
        
        # Count by type
        job_postings = db.query(Job).count()
        developers = db.query(Developer).count()
        
        # Application stats with time periods
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(weeks=1)
        one_month_ago = now - timedelta(days=30)
        
        # Job applications
        total_applied_jobs = db.query(Job).filter(Job.is_applied == True).count()
        daily_applied_jobs = db.query(Job).filter(
            Job.is_applied == True,
            Job.applied_at >= one_day_ago
        ).count()
        weekly_applied_jobs = db.query(Job).filter(
            Job.is_applied == True,
            Job.applied_at >= one_week_ago
        ).count()
        monthly_applied_jobs = db.query(Job).filter(
            Job.is_applied == True,
            Job.applied_at >= one_month_ago
        ).count()
        
        # Developer contacts
        total_contacted_developers = db.query(Developer).filter(Developer.is_contacted == True).count()
        daily_contacted_developers = db.query(Developer).filter(
            Developer.is_contacted == True,
            Developer.contacted_at >= one_day_ago
        ).count()
        weekly_contacted_developers = db.query(Developer).filter(
            Developer.is_contacted == True,
            Developer.contacted_at >= one_week_ago
        ).count()
        monthly_contacted_developers = db.query(Developer).filter(
            Developer.is_contacted == True,
            Developer.contacted_at >= one_month_ago
        ).count()
        
        return {
            "total_channels": db.query(Channel).filter(Channel.is_active == True).count(),
            "total_messages": db.query(Message).count(),
            "job_postings": job_postings,
            "developers": developers,
            "applications": {
                "jobs": {
                    "total": total_applied_jobs,
                    "daily": daily_applied_jobs,
                    "weekly": weekly_applied_jobs,
                    "monthly": monthly_applied_jobs,
                },
            },
            "contacts": {
                "developers": {
                    "total": total_contacted_developers,
                    "daily": daily_contacted_developers,
                    "weekly": weekly_contacted_developers,
                    "monthly": monthly_contacted_developers,
                },
            },
            "unreviewed_jobs": db.query(Job).filter(Job.is_reviewed == False).count(),
            "unreviewed_developers": db.query(Developer).filter(Developer.is_reviewed == False).count(),
            "pending_analysis": pending_analysis,
            "ollama_available": ollama_available,
            "recent_runs": db.query(AnalysisRun).order_by(
                AnalysisRun.started_at.desc()
            ).limit(5).count(),
        }
