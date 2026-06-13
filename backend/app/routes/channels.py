"""Channel-related API routes."""

from typing import Optional
from fastapi import Depends, Form, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Channel, Message, Job


def register_channel_routes(app):
    """Register channel-related routes."""

    @app.post("/api/channels")
    async def add_channel(
        username: str = Form(...),
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        telegram_account_id: Optional[int] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Add a new channel."""
        try:
            # Normalize username
            username = username.strip()
            if not username.startswith("@"):
                username = f"@{username}"

            # Check if exists
            result = await db.execute(select(Channel).filter(Channel.username == username))
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="Channel already exists")

            channel = Channel(
                username=username,
                name=name,
                description=description,
                telegram_account_id=telegram_account_id,
            )
            db.add(channel)
            await db.commit()
            await db.refresh(channel)

            return {"success": True, "channel": {"id": channel.id, "username": channel.username}}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to add channel: {str(e)}")

    @app.delete("/api/channels/{channel_id}")
    async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
        """Delete a channel."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            await db.delete(channel)
            await db.commit()

            return {"success": True}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete channel: {str(e)}")

    @app.put("/api/channels/{channel_id}")
    async def update_channel(
        channel_id: int,
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        telegram_account_id: Optional[int] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Update a channel."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            if name is not None:
                channel.name = name
            if description is not None:
                channel.description = description
            if telegram_account_id is not None:
                channel.telegram_account_id = telegram_account_id

            await db.commit()

            return {"success": True, "channel": {"id": channel.id, "username": channel.username}}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update channel: {str(e)}")

    @app.post("/api/channels/{channel_id}/toggle")
    async def toggle_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
        """Toggle channel active status."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            channel.is_active = not channel.is_active
            await db.commit()

            return {"success": True, "is_active": channel.is_active}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle channel: {str(e)}")

    @app.get("/api/channels")
    async def api_channels(
        limit: int = 10,
        offset: int = 0,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        db: AsyncSession = Depends(get_db),
    ):
        """Get channels as JSON with pagination, search, and filters."""
        # Build base query with subqueries for counts
        message_count_subq = (
            select(func.count())
            .where(Message.channel_id == Channel.id)
            .correlate(Channel)
            .scalar_subquery()
        )
        job_count_subq = (
            select(func.count())
            .where(Job.channel_id == Channel.id)
            .correlate(Channel)
            .scalar_subquery()
        )
        pending_count_subq = (
            select(func.count())
            .where(Message.channel_id == Channel.id, Message.analysis_status == "pending")
            .correlate(Channel)
            .scalar_subquery()
        )

        query = select(
            Channel,
            message_count_subq.label("message_count"),
            job_count_subq.label("job_count"),
            pending_count_subq.label("pending_count")
        )
        count_query = select(func.count()).select_from(Channel)

        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (Channel.username.ilike(search_pattern)) |
                (Channel.name.ilike(search_pattern)) |
                (Channel.description.ilike(search_pattern))
            )
            count_query = count_query.where(
                (Channel.username.ilike(search_pattern)) |
                (Channel.name.ilike(search_pattern)) |
                (Channel.description.ilike(search_pattern))
            )

        # Apply active filter
        if is_active is not None:
            query = query.where(Channel.is_active == is_active)
            count_query = count_query.where(Channel.is_active == is_active)

        # Get total count
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get channels with pagination, sorted by job_count DESC, message_count DESC
        channels_result = await db.execute(
            query.order_by(
                job_count_subq.desc(),
                message_count_subq.desc(),
                Channel.id
            ).offset(offset).limit(limit)
        )
        channels = channels_result.all()

        # Build response data
        channels_data = []
        for row in channels:
            channel = row[0]
            message_count = row[1] or 0
            job_count = row[2] or 0
            pending_count = row[3] or 0

            channels_data.append({
                "id": channel.id,
                "username": channel.username,
                "name": channel.name,
                "description": channel.description,
                "is_active": channel.is_active,
                "is_listened": channel.is_listened,
                "telegram_account_id": channel.telegram_account_id,
                "message_count": message_count,
                "pending_count": pending_count,
                "job_count": job_count,
                "last_fetch_new_count": channel.last_fetch_new_count,
                "last_fetch_at": channel.last_fetch_at.isoformat() if channel.last_fetch_at else None,
            })

        return {
            "channels": channels_data,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
