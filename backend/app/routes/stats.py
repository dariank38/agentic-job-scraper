"""Stats-related API routes."""

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db
from app.models import AnalysisRun, Channel, Job, Developer, Message


def register_stats_routes(app):
    """Register stats-related routes."""

    @app.get("/api/stats")
    async def api_stats(db: AsyncSession = Depends(get_db)):
        """Get dashboard statistics."""
        from services.ollama_service import is_ollama_available
        
        # Get channel counts
        total_channels_result = await db.execute(
            select(func.count()).select_from(Channel)
        )
        total_channels = total_channels_result.scalar()
        
        active_channels_result = await db.execute(
            select(func.count()).select_from(Channel).filter(Channel.is_active == True)
        )
        active_channels = active_channels_result.scalar()

        # Get job counts
        job_postings_result = await db.execute(
            select(func.count()).select_from(Job)
        )
        job_postings = job_postings_result.scalar()
        
        applied_jobs_result = await db.execute(
            select(func.count()).select_from(Job).filter(Job.is_applied == True)
        )
        applied_jobs = applied_jobs_result.scalar()

        # Get developer counts
        developers_result = await db.execute(
            select(func.count()).select_from(Developer)
        )
        developers = developers_result.scalar()
        
        contacted_developers_result = await db.execute(
            select(func.count()).select_from(Developer).filter(Developer.is_contacted == True)
        )
        contacted_developers = contacted_developers_result.scalar()

        # Get message counts by analysis_status
        total_messages_result = await db.execute(
            select(func.count()).select_from(Message)
        )
        total_messages = total_messages_result.scalar()
        
        # Count by status
        pending_messages_result = await db.execute(
            select(func.count()).select_from(Message).filter(Message.analysis_status == "pending")
        )
        pending_messages = pending_messages_result.scalar() or 0
        
        analyzed_messages_result = await db.execute(
            select(func.count()).select_from(Message).filter(Message.analysis_status == "analyzed")
        )
        analyzed_messages = analyzed_messages_result.scalar() or 0
        
        skipped_messages_result = await db.execute(
            select(func.count()).select_from(Message).filter(Message.analysis_status == "skipped")
        )
        skipped_messages = skipped_messages_result.scalar() or 0

        # Get recent analysis runs
        recent_runs_result = await db.execute(
            select(AnalysisRun)
            .order_by(AnalysisRun.started_at.desc())
            .limit(10)
        )
        recent_runs = recent_runs_result.scalars().all()

        # Get pending reanalysis count
        pending_result = await db.execute(
            select(func.count()).select_from(Message).filter(Message.needs_reanalysis == True)
        )
        pending_reanalysis = pending_result.scalar()

        # Get pending by channel
        pending_by_channel_result = await db.execute(
            select(Channel.id, Channel.username, func.count(Message.id).label("count"))
            .join(Message, Channel.id == Message.channel_id)
            .filter(Message.needs_reanalysis == True)
            .group_by(Channel.id, Channel.username)
        )
        pending_by_channel = [
            {"channel_id": row.id, "username": row.username, "count": row.count}
            for row in pending_by_channel_result.all()
        ]

        return {
            "total_channels": total_channels,
            "active_channels": active_channels,
            "job_postings": job_postings,
            "developers": developers,
            "total_messages": total_messages,
            "analyzed_messages": analyzed_messages,
            "pending_messages": pending_messages,
            "skipped_messages": skipped_messages,
            "applications": {
                "jobs": {
                    "total": applied_jobs,
                    "applied": applied_jobs
                },
                "developers": {
                    "total": developers,
                    "contacted": contacted_developers
                }
            },
            "ollama_available": await is_ollama_available(),
            "recent_runs": [
                {
                    "id": run.id,
                    "run_type": run.run_type,
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
