"""Website source CRUD API routes."""

import logging
from typing import Optional

from fastapi import Depends, Form, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db
from app.models import Developer, Job, Message, WebsiteSource

logger = logging.getLogger(__name__)


def detect_site_type(url: str) -> str:
    url_lower = url.lower()
    if 'v2ex.com' in url_lower:
        return 'v2ex'
    elif 'eleduck.com' in url_lower:
        return 'eleduck'
    elif 'bossjob.com' in url_lower:
        return 'bossjob'
    return 'generic'


def register_website_source_crud_routes(app):

    @app.get("/api/website-sources")
    async def get_website_sources(db: AsyncSession = Depends(get_db)):
        message_count_subq = select(func.count()).where(Message.website_source_id == WebsiteSource.id).correlate(WebsiteSource).scalar_subquery()
        job_count_subq = select(func.count()).where(Job.website_source_id == WebsiteSource.id, Job.is_hidden == False).correlate(WebsiteSource).scalar_subquery()
        pending_count_subq = select(func.count()).where(Message.website_source_id == WebsiteSource.id, Message.analysis_status == "pending").correlate(WebsiteSource).scalar_subquery()

        sources_result = await db.execute(
            select(WebsiteSource, message_count_subq.label("message_count"), job_count_subq.label("job_count"), pending_count_subq.label("pending_count"))
            .order_by(job_count_subq.desc(), message_count_subq.desc(), WebsiteSource.id)
        )
        sources = sources_result.all()
        return {
            "success": True,
            "sources": [
                {
                    "id": row[0].id,
                    "name": row[0].name,
                    "url": row[0].url,
                    "site_type": row[0].site_type,
                    "is_active": row[0].is_active,
                    "last_fetch_new_count": row[0].last_fetch_new_count,
                    "last_fetch_at": row[0].last_fetch_at.isoformat() if row[0].last_fetch_at else None,
                    "job_count": row[2] or 0,
                    "message_count": row[1] or 0,
                    "pending_count": row[3] or 0,
                }
                for row in sources
            ],
        }

    @app.post("/api/website-sources")
    async def add_website_source(name: str = Form(...), url: str = Form(...), site_type: Optional[str] = Form(None), db: AsyncSession = Depends(get_db)):
        try:
            if not site_type:
                site_type = detect_site_type(url)
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.url == url))
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Website source already exists")
            source = WebsiteSource(name=name, url=url, site_type=site_type)
            db.add(source)
            await db.commit()
            await db.refresh(source)
            return {"success": True, "source": {"id": source.id, "name": source.name, "url": source.url, "site_type": source.site_type}}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/website-sources/{source_id}")
    async def delete_website_source(source_id: int, db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")
            await db.execute(delete(Job).where(Job.website_source_id == source_id))
            await db.execute(delete(Developer).where(Developer.website_source_id == source_id))
            await db.execute(delete(Message).where(Message.website_source_id == source_id))
            await db.delete(source)
            await db.commit()
            return {"success": True, "message": "Website source deleted"}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/api/website-sources/{source_id}")
    async def update_website_source(
        source_id: int,
        name: Optional[str] = Form(None),
        url: Optional[str] = Form(None),
        is_active: Optional[bool] = Form(None),
        extraction_prompt: Optional[str] = Form(None),
        cookies: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")
            if name is not None:
                source.name = name
            if url is not None:
                source.url = url
                source.site_type = detect_site_type(url)
            if is_active is not None:
                source.is_active = is_active
            if extraction_prompt is not None:
                source.extraction_prompt = extraction_prompt
            if cookies is not None:
                source.cookies = cookies
            source.updated_at = func.now()
            await db.commit()
            return {"success": True, "message": "Website source updated"}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/{source_id}/toggle")
    async def toggle_website_source(source_id: int, db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")
            source.is_active = not source.is_active
            source.updated_at = func.now()
            await db.commit()
            return {"success": True, "is_active": source.is_active}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
