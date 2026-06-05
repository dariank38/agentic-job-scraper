"""API routes for job scraper."""

from typing import Optional
from fastapi import HTTPException, Depends, Form
from sqlalchemy.orm import Session

from app.connection import get_db
from app.models import Channel, Job, Message, AnalysisRun
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
        from datetime import datetime

        # Get messages that need re-analysis
        messages = db.query(Message).filter(Message.needs_reanalysis == True).all()

        if not messages:
            return {"success": True, "reanalyzed": 0, "message": "No messages need re-analysis"}

        reanalyzed_count = 0

        for message in messages:
            if not message.text:
                continue

            analysis = await analyze_message(message.text)

            if analysis is None:
                continue

            category = analysis.get("category", "other")
            extracted = analysis.get("extracted", {})

            # Check if job already exists
            existing_job = db.query(Job).filter(Job.message_id == message.id).first()

            if existing_job:
                # Update existing job
                existing_job.category = category
                existing_job.confidence = analysis.get("confidence")
                existing_job.ai_title = extracted.get("title")
                existing_job.ai_company = extracted.get("company")
                existing_job.ai_company_link = extracted.get("company_link")
                existing_job.ai_location = extracted.get("location")
                existing_job.ai_remote = extracted.get("remote")
                existing_job.ai_role_type = extracted.get("role_type")
                existing_job.ai_skills = extracted.get("skills", [])
                existing_job.ai_contact = extracted.get("contact")
                existing_job.ai_contact_type = extracted.get("contact_type")
                existing_job.ai_summary = extracted.get("summary")
                existing_job.analyzed_at = datetime.utcnow()
            else:
                # Create new job
                job = Job(
                    message_id=message.id,
                    channel_id=message.channel_id,
                    category=category,
                    confidence=analysis.get("confidence"),
                    ai_title=extracted.get("title"),
                    ai_company=extracted.get("company"),
                    ai_company_link=extracted.get("company_link"),
                    ai_location=extracted.get("location"),
                    ai_remote=extracted.get("remote"),
                    ai_role_type=extracted.get("role_type"),
                    ai_skills=extracted.get("skills", []),
                    ai_contact=extracted.get("contact"),
                    ai_contact_type=extracted.get("contact_type"),
                    ai_summary=extracted.get("summary"),
                )
                db.add(job)

            # Clear re-analysis flag
            message.needs_reanalysis = False
            reanalyzed_count += 1

        db.commit()

        return {"success": True, "reanalyzed": reanalyzed_count}

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
        category: Optional[str] = None,
        remote: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
        db: Session = Depends(get_db),
    ):
        """Get jobs as JSON."""
        query = db.query(Job).join(Channel).filter(Channel.is_active == True)

        if category:
            query = query.filter(Job.category == category)

        if remote is not None:
            query = query.filter(Job.ai_remote == remote)

        total = query.count()
        jobs = query.order_by(Job.analyzed_at.desc()).offset(offset).limit(limit).all()

        return {
            "jobs": [job.to_dict() for job in jobs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

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
        return {
            "total_channels": db.query(Channel).filter(Channel.is_active == True).count(),
            "total_messages": db.query(Message).count(),
            "total_jobs": db.query(Job).filter(
                Job.category.in_(["job_posting", "remote_work"])
            ).count(),
            "unreviewed_jobs": db.query(Job).filter(
                Job.is_reviewed == False,
                Job.category.in_(["job_posting", "remote_work"]),
            ).count(),
            "recent_runs": db.query(AnalysisRun).order_by(
                AnalysisRun.started_at.desc()
            ).limit(5).count(),
        }
