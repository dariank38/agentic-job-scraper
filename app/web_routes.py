"""Web UI routes for job scraper."""

from typing import Optional
from pathlib import Path
from fastapi import Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.connection import get_db
from app.models import Channel, Job, Developer, Message

# Initialize templates once at module level
_BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def register_web_routes(app):

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request, db: Session = Depends(get_db)):
        """Main dashboard page."""
        channels = db.query(Channel).filter(Channel.is_active == True).all()
        recent_jobs = db.query(Job).order_by(Job.analyzed_at.desc()).limit(10).all()

        from datetime import datetime, timedelta
        
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
        
        stats = {
            "total_channels": db.query(Channel).filter(Channel.is_active == True).count(),
            "total_messages": db.query(Message).count(),
            "job_postings": db.query(Job).count(),
            "developers": db.query(Developer).count(),
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
        }

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "channels": channels,
                "recent_jobs": recent_jobs,
                "stats": stats,
            },
        )

    @app.get("/channels", response_class=HTMLResponse)
    async def channels_page(request: Request, db: Session = Depends(get_db)):
        """Channels management page."""
        channels = db.query(Channel).all()
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
        db: Session = Depends(get_db),
    ):
        """Developers listing page."""
        query = db.query(Developer).join(Channel).filter(Channel.is_active == True)

        if looking_for_work is not None:
            query = query.filter(Developer.looking_for_work == looking_for_work)

        developers = query.order_by(Developer.analyzed_at.desc()).all()

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
        db: Session = Depends(get_db),
    ):
        """Jobs listing page."""
        query = db.query(Job).join(Channel).filter(Channel.is_active == True)

        if remote is not None:
            query = query.filter(Job.is_remote == remote)

        jobs = query.order_by(Job.analyzed_at.desc()).all()

        return templates.TemplateResponse(
            request,
            "jobs.html",
            {
                "jobs": jobs,
                "remote_filter": remote,
            },
        )

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_detail(request: Request, job_id: int, db: Session = Depends(get_db)):
        """Job detail page."""
        job = db.query(Job).get(job_id)
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
        db: Session = Depends(get_db),
    ):
        """Mark job as reviewed."""
        job = db.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job.is_reviewed = True
        job.is_approved = is_approved
        job.notes = notes
        db.commit()

        return {"success": True}

    @app.get("/developers/{developer_id}", response_class=HTMLResponse)
    async def developer_detail(request: Request, developer_id: int, db: Session = Depends(get_db)):
        """Developer detail page."""
        developer = db.query(Developer).get(developer_id)
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
        db: Session = Depends(get_db),
    ):
        """Mark developer as reviewed."""
        developer = db.query(Developer).get(developer_id)
        if not developer:
            raise HTTPException(status_code=404, detail="Developer not found")

        developer.is_reviewed = True
        developer.is_approved = is_approved
        developer.notes = notes
        db.commit()

        return {"success": True}
