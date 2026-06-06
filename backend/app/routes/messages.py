"""Message-related API routes."""

from typing import Optional
from fastapi import Depends
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
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = Depends(get_db),
    ):
        """Get messages as JSON."""
        query = select(Message)

        if channel_id:
            query = query.filter(Message.channel_id == channel_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get messages with pagination, eagerly load channel
        messages_query = query.options(
            selectinload(Message.channel)
        ).order_by(Message.date.desc()).offset(offset).limit(limit)
        messages_result = await db.execute(messages_query)
        messages = messages_result.scalars().all()

        return {
            "messages": [msg.to_dict() for msg in messages],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
