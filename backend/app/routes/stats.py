"""Stats-related API routes."""

from datetime import datetime, timedelta
from fastapi import Depends, Query
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

    @app.get("/api/daily-jobs")
    async def api_daily_jobs(
        days: int = Query(30, description="Number of days to include"),
        db: AsyncSession = Depends(get_db),
    ):
        """Get daily job postings count by channel for the last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(
                func.date(Message.date).label('date'),
                Channel.username.label('channel'),
                func.count(Job.id).label('count')
            )
            .join(Job, Job.message_id == Message.id)
            .join(Channel, Channel.id == Job.channel_id)
            .filter(Message.date >= cutoff_date)
            .group_by(func.date(Message.date), Channel.username)
            .order_by(func.date(Message.date).desc())
        )

        data = {}
        for row in result.all():
            date_str = str(row.date)
            if date_str not in data:
                data[date_str] = {}
            data[date_str][row.channel] = row.count

        return {"data": data, "days": days}

    @app.get("/api/daily-developers-contacted")
    async def api_daily_developers_contacted(
        days: int = Query(30, description="Number of days to include"),
        db: AsyncSession = Depends(get_db),
    ):
        """Get daily developers contacted count for the last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(
                func.date(Developer.contacted_at).label('date'),
                func.count(Developer.id).label('count')
            )
            .filter(Developer.is_contacted == True, Developer.contacted_at >= cutoff_date)
            .group_by(func.date(Developer.contacted_at))
            .order_by(func.date(Developer.contacted_at).desc())
        )

        data = {str(row.date): row.count for row in result.all()}
        return {"data": data, "days": days}

    @app.get("/api/daily-stats-table")
    async def api_daily_stats_table(
        days: int = Query(7, description="Number of days to include"),
        db: AsyncSession = Depends(get_db),
    ):
        """Get combined daily stats for table display (job postings, developers contacted, jobs applied)."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get daily job postings
        jobs_result = await db.execute(
            select(
                func.date(Job.created_at).label('date'),
                func.count(Job.id).label('count')
            )
            .filter(Job.created_at >= cutoff_date)
            .group_by(func.date(Job.created_at))
            .order_by(func.date(Job.created_at).desc())
        )
        jobs_data = {str(row.date): row.count for row in jobs_result.all()}

        # Get daily developers contacted
        developers_result = await db.execute(
            select(
                func.date(Developer.contacted_at).label('date'),
                func.count(Developer.id).label('count')
            )
            .filter(Developer.is_contacted == True, Developer.contacted_at >= cutoff_date)
            .group_by(func.date(Developer.contacted_at))
            .order_by(func.date(Developer.contacted_at).desc())
        )
        developers_data = {str(row.date): row.count for row in developers_result.all()}

        # Get daily jobs applied
        applied_result = await db.execute(
            select(
                func.date(Job.applied_at).label('date'),
                func.count(Job.id).label('count')
            )
            .filter(Job.is_applied == True, Job.applied_at >= cutoff_date)
            .group_by(func.date(Job.applied_at))
            .order_by(func.date(Job.applied_at).desc())
        )
        applied_data = {str(row.date): row.count for row in applied_result.all()}

        # Combine all dates
        all_dates = set(jobs_data.keys()) | set(developers_data.keys()) | set(applied_data.keys())
        sorted_dates = sorted(all_dates, reverse=True)

        table_data = [
            {
                "date": date,
                "job_postings": jobs_data.get(date, 0),
                "developers_contacted": developers_data.get(date, 0),
                "jobs_applied": applied_data.get(date, 0),
            }
            for date in sorted_dates
        ]

        return {"data": table_data, "days": days}

    @app.get("/api/daily-jobs-applied")
    async def api_daily_jobs_applied(
        days: int = Query(30, description="Number of days to include"),
        db: AsyncSession = Depends(get_db),
    ):
        """Get daily jobs applied count for the last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(
                func.date(Job.applied_at).label('date'),
                func.count(Job.id).label('count')
            )
            .filter(Job.is_applied == True, Job.applied_at >= cutoff_date)
            .group_by(func.date(Job.applied_at))
            .order_by(func.date(Job.applied_at).desc())
        )

        data = {str(row.date): row.count for row in result.all()}
        return {"data": data, "days": days}
