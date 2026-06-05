"""Web UI routes for job scraper."""

from typing import Optional
from pathlib import Path
from fastapi import Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.connection import get_db
from app.models import Channel, Job, Message

# Initialize templates once at module level
_BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def register_web_routes(app):

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request, db: Session = Depends(get_db)):
        """Main dashboard page."""
        channels = db.query(Channel).filter(Channel.is_active == True).all()
        recent_jobs = db.query(Job).order_by(Job.analyzed_at.desc()).limit(10).all()

        stats = {
            "total_channels": db.query(Channel).filter(Channel.is_active == True).count(),
            "total_messages": db.query(Message).count(),
            "total_jobs": db.query(Job).filter(
                Job.category.in_(["job_posting", "remote_work"])
            ).count(),
            "unreviewed_jobs": db.query(Job).filter(
                Job.is_reviewed == False,
                Job.category.in_(["job_posting", "remote_work"]),
            ).count(),
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

    @app.get("/jobs", response_class=HTMLResponse)
    async def jobs_page(
        request: Request,
        category: Optional[str] = None,
        remote: Optional[bool] = None,
        db: Session = Depends(get_db),
    ):
        """Jobs listing page."""
        query = db.query(Job).join(Channel).filter(Channel.is_active == True)

        if category:
            query = query.filter(Job.category == category)

        if remote is not None:
            query = query.filter(Job.ai_remote == remote)

        jobs = query.order_by(Job.analyzed_at.desc()).all()
        categories = ["job_posting", "remote_work", "contact_info", "other"]

        return templates.TemplateResponse(
            request,
            "jobs.html",
            {
                "jobs": jobs,
                "categories": categories,
                "selected_category": category,
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
