"""Message-related API routes."""

from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Message


def register_message_routes(app):
    """Register message-related routes."""

    @app.get("/api/messages")
    async def api_messages(
        channel_id: Optional[int] = None,
        website_source_id: Optional[int] = None,
        search: Optional[str] = None,
        analysis_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get messages as JSON with search and filters."""
        query = select(Message)

        if channel_id:
            query = query.filter(Message.channel_id == channel_id)

        if website_source_id:
            query = query.filter(Message.website_source_id == website_source_id)

        # Apply search filter - search all text fields
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (Message.text.ilike(search_pattern)) |
                (Message.sender_username.ilike(search_pattern)) |
                (Message.sender_first_name.ilike(search_pattern))
            )

        # Apply status filter
        if analysis_status:
            query = query.filter(Message.analysis_status == analysis_status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get messages with pagination, eagerly load channel, website_source, job, and developer
        messages_query = query.options(
            selectinload(Message.channel),
            selectinload(Message.website_source),
            selectinload(Message.job),
            selectinload(Message.developer)
        ).order_by(Message.date.desc()).offset(offset).limit(limit)
        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()

        return {
            "messages": [msg.to_dict() for msg in messages],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.delete("/api/messages/{message_id}")
    async def api_delete_message(message_id: int, db: AsyncSession = Depends(get_db)):
        """Delete a message and its associated job/developer."""
        try:
            result = await db.execute(select(Message).filter(Message.id == message_id))
            message = result.scalar_one_or_none()
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            await db.delete(message)
            await db.commit()

            return {"success": True}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")
