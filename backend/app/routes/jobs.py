"""Job-related API routes."""

from typing import Optional
from fastapi import Depends, Form, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Job, Message


def register_job_routes(app):
    """Register job-related routes."""

    @app.get("/api/jobs")
    async def api_jobs(
        search: Optional[str] = None,
        is_applied: Optional[bool] = None,
        limit: int = 10,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get jobs as JSON with search and filters."""
        from app.models import Channel

        query = select(Job).join(Channel).filter(Channel.is_active == True)

        if is_applied is not None:
            query = query.filter(Job.is_applied == is_applied)

        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (Job.title.ilike(search_pattern)) |
                (Job.company.ilike(search_pattern)) |
                (Job.location.ilike(search_pattern))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get jobs with pagination, eagerly load message and channel
        # Order by message date (when posted on Telegram) for most recent first
        jobs_query = query.options(
            selectinload(Job.message),
            selectinload(Job.channel)
        ).join(Job.message).order_by(Message.date.desc()).offset(offset).limit(limit)
        jobs_result = await db.execute(jobs_query)
        jobs = jobs_result.scalars().all()

        return {
            "jobs": [job.to_dict() for job in jobs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/jobs/{job_id}")
    async def api_job_detail(job_id: int, db: AsyncSession = Depends(get_db)):
        """Get job detail as JSON."""
        result = await db.execute(
            select(Job).options(
                selectinload(Job.channel),
                selectinload(Job.message)
            ).filter(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job": job.to_dict()}

    @app.post("/api/jobs/{job_id}/review")
    async def api_review_job(
        job_id: int,
        is_approved: bool = Form(...),
        notes: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Mark job as reviewed."""
        try:
            result = await db.execute(select(Job).filter(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            job.is_reviewed = True
            job.is_approved = is_approved
            job.notes = notes
            await db.commit()

            return {"success": True}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to review job: {str(e)}")

    @app.post("/api/jobs/{job_id}/toggle-applied")
    async def api_toggle_job_applied(
        job_id: int,
        notes: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Toggle job applied status with optional notes."""
        try:
            result = await db.execute(select(Job).filter(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            job.is_applied = not job.is_applied
            if job.is_applied:
                from datetime import datetime
                job.applied_at = datetime.utcnow()
                job.notes = notes
            else:
                job.applied_at = None
                job.notes = None
            await db.commit()

            return {"success": True, "is_applied": job.is_applied}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle applied status: {str(e)}")
