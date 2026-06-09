"""Developer-related API routes."""

from typing import Optional
from fastapi import Depends, Form, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Developer


def register_developer_routes(app):
    """Register developer-related routes."""

    @app.get("/api/developers")
    async def api_developers(
        looking_for_work: Optional[bool] = None,
        is_contacted: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get developers as JSON with search and filters."""
        from app.models import Channel

        query = select(Developer).join(Channel).filter(Channel.is_active == True)

        if looking_for_work is not None:
            query = query.filter(Developer.looking_for_work == looking_for_work)

        if is_contacted is not None:
            query = query.filter(Developer.is_contacted == is_contacted)

        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (Developer.name.ilike(search_pattern))
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get developers with pagination, eagerly load message and channel
        developers_query = query.options(
            selectinload(Developer.message),
            selectinload(Developer.channel)
        ).order_by(Developer.analyzed_at.desc()).offset(offset).limit(limit)
        developers_result = await db.execute(developers_query)
        developers = developers_result.scalars().all()

        return {
            "developers": [dev.to_dict() for dev in developers],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/developers/{developer_id}")
    async def api_developer_detail(developer_id: int, db: AsyncSession = Depends(get_db)):
        """Get developer detail as JSON."""
        result = await db.execute(
            select(Developer).options(
                selectinload(Developer.channel),
                selectinload(Developer.message)
            ).filter(Developer.id == developer_id)
        )
        developer = result.scalar_one_or_none()
        if not developer:
            raise HTTPException(status_code=404, detail="Developer not found")
        return {"developer": developer.to_dict()}

    @app.post("/api/developers/{developer_id}/review")
    async def api_review_developer(
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

    @app.post("/api/developers/{developer_id}/toggle-contacted")
    async def api_toggle_developer_contacted(
        developer_id: int,
        notes: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Toggle developer contacted status with optional notes."""
        try:
            result = await db.execute(
                select(Developer).options(
                    selectinload(Developer.channel),
                    selectinload(Developer.message)
                ).filter(Developer.id == developer_id)
            )
            developer = result.scalar_one_or_none()
            if not developer:
                raise HTTPException(status_code=404, detail="Developer not found")

            developer.is_contacted = not developer.is_contacted
            if developer.is_contacted:
                from datetime import datetime
                developer.contacted_at = datetime.utcnow()
                developer.notes = notes
            else:
                developer.contacted_at = None
                developer.notes = None
            await db.commit()
            await db.refresh(developer)

            return {"success": True, "is_contacted": developer.is_contacted, "developer": developer.to_dict()}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle contacted status: {str(e)}")
