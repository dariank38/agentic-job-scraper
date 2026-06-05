"""Web UI routes for job scraper."""

from typing import Optional
from pathlib import Path
from fastapi import Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Channel, Job, Developer, Message

# Initialize templates once at module level
_BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def register_web_routes(app):

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
        """Main dashboard page."""
        channels_result = await db.execute(select(Channel).filter(Channel.is_active == True))
        channels = channels_result.scalars().all()
        
        # Build channels with counts (much faster than eager loading all relationships)
        channels_with_counts = []
        for channel in channels:
            messages_count_result = await db.execute(
                select(func.count()).select_from(Message).filter(Message.channel_id == channel.id)
            )
            messages_count = messages_count_result.scalar()
            
            jobs_count_result = await db.execute(
                select(func.count()).select_from(Job).filter(Job.channel_id == channel.id)
            )
            jobs_count = jobs_count_result.scalar()
            
            channels_with_counts.append({
                "id": channel.id,
                "username": channel.username,
                "name": channel.name,
                "messages_count": messages_count,
                "jobs_count": jobs_count,
            })
        
        recent_jobs_result = await db.execute(
            select(Job).options(selectinload(Job.channel)).order_by(Job.analyzed_at.desc()).limit(10)
        )
        recent_jobs = recent_jobs_result.scalars().all()

        from datetime import datetime, timedelta
        
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
        
        # Stats counts
        total_channels_result = await db.execute(
            select(func.count()).select_from(Channel).filter(Channel.is_active == True)
        )
        total_channels = total_channels_result.scalar()
        
        total_messages_result = await db.execute(select(func.count()).select_from(Message))
        total_messages = total_messages_result.scalar()
        
        job_postings_result = await db.execute(select(func.count()).select_from(Job))
        job_postings = job_postings_result.scalar()
        
        developers_result = await db.execute(select(func.count()).select_from(Developer))
        developers = developers_result.scalar()
        
        unreviewed_jobs_result = await db.execute(
            select(func.count()).select_from(Job).filter(Job.is_reviewed == False)
        )
        unreviewed_jobs = unreviewed_jobs_result.scalar()
        
        unreviewed_developers_result = await db.execute(
            select(func.count()).select_from(Developer).filter(Developer.is_reviewed == False)
        )
        unreviewed_developers = unreviewed_developers_result.scalar()
        
        stats = {
            "total_channels": total_channels,
            "total_messages": total_messages,
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
            "unreviewed_jobs": unreviewed_jobs,
            "unreviewed_developers": unreviewed_developers,
        }

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "channels": channels_with_counts,
                "recent_jobs": recent_jobs,
                "stats": stats,
            },
        )

    @app.get("/channels", response_class=HTMLResponse)
    async def channels_page(request: Request, db: AsyncSession = Depends(get_db)):
        """Channels management page."""
        result = await db.execute(
            select(Channel).options(
                selectinload(Channel.messages),
                selectinload(Channel.jobs),
                selectinload(Channel.developers)
            )
        )
        channels = result.scalars().all()
        return templates.TemplateResponse(
            request,
            "channels.html",
            {
                "channels": channels,
            },
        )

    @app.get("/developers", response_class=HTMLResponse)
    async def developers_page(
        request: Request,
        looking_for_work: Optional[bool] = None,
        db: AsyncSession = Depends(get_db),
    ):
        """Developers listing page."""
        query = select(Developer).join(Channel).filter(Channel.is_active == True).options(
            selectinload(Developer.channel),
            selectinload(Developer.message)
        )

        if looking_for_work is not None:
            query = query.filter(Developer.looking_for_work == looking_for_work)

        developers_result = await db.execute(query.order_by(Developer.analyzed_at.desc()))
        developers = developers_result.scalars().all()

        return templates.TemplateResponse(
            request,
            "developers.html",
            {
                "developers": developers,
                "looking_for_work_filter": looking_for_work,
            },
        )

    @app.get("/jobs", response_class=HTMLResponse)
    async def jobs_page(
        request: Request,
        remote: Optional[bool] = None,
        db: AsyncSession = Depends(get_db),
    ):
        """Jobs listing page."""
        query = select(Job).join(Channel).filter(Channel.is_active == True).options(
            selectinload(Job.channel),
            selectinload(Job.message)
        )

        if remote is not None:
            query = query.filter(Job.is_remote == remote)

        jobs_result = await db.execute(query.order_by(Job.analyzed_at.desc()))
        jobs = jobs_result.scalars().all()

        return templates.TemplateResponse(
            request,
            "jobs.html",
            {
                "jobs": jobs,
                "remote_filter": remote,
            },
        )

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_detail(request: Request, job_id: int, db: AsyncSession = Depends(get_db)):
        """Job detail page."""
        result = await db.execute(select(Job).filter(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return templates.TemplateResponse(
            request,
            "job_detail.html",
            {
                "job": job,
            },
        )

    @app.post("/jobs/{job_id}/review")
    async def review_job(
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

    @app.get("/developers/{developer_id}", response_class=HTMLResponse)
    async def developer_detail(request: Request, developer_id: int, db: AsyncSession = Depends(get_db)):
        """Developer detail page."""
        result = await db.execute(select(Developer).filter(Developer.id == developer_id))
        developer = result.scalar_one_or_none()
        if not developer:
            raise HTTPException(status_code=404, detail="Developer not found")

        return templates.TemplateResponse(
            request,
            "developer_detail.html",
            {
                "developer": developer,
            },
        )

    @app.post("/developers/{developer_id}/review")
    async def review_developer(
        developer_id: int,
        is_approved: bool = Form(...),
        notes: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Mark developer as reviewed."""
        try:
            result = await db.execute(select(Developer).filter(Developer.id == developer_id))
            developer = result.scalar_one_or_none()
            if not developer:
                raise HTTPException(status_code=404, detail="Developer not found")

            developer.is_reviewed = True
            developer.is_approved = is_approved
            developer.notes = notes
            await db.commit()

            return {"success": True}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to review developer: {str(e)}")
