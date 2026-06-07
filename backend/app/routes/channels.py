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
        # Build base query
        query = select(Channel)
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

        # Get channels with pagination
        channels_result = await db.execute(query.order_by(Channel.id).offset(offset).limit(limit))
        channels = channels_result.scalars().all()

        # Get counts for each channel using subqueries to avoid join multiplication
        channels_data = []
        for channel in channels:
            # Count messages
            msg_count_result = await db.execute(
                select(func.count()).select_from(Message).filter(Message.channel_id == channel.id)
            )
            message_count = msg_count_result.scalar() or 0

            # Count pending messages (not yet analyzed)
            pending_count_result = await db.execute(
                select(func.count()).select_from(Message).filter(
                    Message.channel_id == channel.id,
                    Message.analysis_status == "pending"
                )
            )
            pending_count = pending_count_result.scalar() or 0

            # Count jobs
            job_count_result = await db.execute(
                select(func.count()).select_from(Job).filter(Job.channel_id == channel.id)
            )
            job_count = job_count_result.scalar() or 0

            channels_data.append({
                "id": channel.id,
                "username": channel.username,
                "name": channel.name,
                "description": channel.description,
                "is_active": channel.is_active,
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
