"""Message-related API routes."""

from typing import Optional
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connection import get_db
from app.models import Message


class BulkDeleteRequest(BaseModel):
    ids: list[int]


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

    @app.get("/api/messages/{message_id}")
    async def api_get_message(message_id: int, db: AsyncSession = Depends(get_db)):
        """Get a single message by ID."""
        result = await db.execute(
            select(Message).options(
                selectinload(Message.channel),
                selectinload(Message.website_source),
                selectinload(Message.job),
                selectinload(Message.developer),
            ).filter(Message.id == message_id)
        )
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"message": message.to_dict()}

    @app.post("/api/messages/bulk-delete")
    async def api_bulk_delete_messages(
        request: BulkDeleteRequest,
        db: AsyncSession = Depends(get_db),
    ):
        """Delete multiple messages and their associated jobs/developers."""
        if not request.ids:
            return {"success": True, "deleted": 0}
        try:
            result = await db.execute(select(Message).filter(Message.id.in_(request.ids)))
            messages = result.scalars().all()
            for message in messages:
                await db.delete(message)
            await db.commit()

            return {"success": True, "deleted": len(messages)}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to bulk delete messages: {str(e)}")

    @app.post("/api/messages/{message_id}/toggle-skip")
    async def api_toggle_skip_message(message_id: int, db: AsyncSession = Depends(get_db)):
        """Toggle manual skip on a message. Skipped messages are excluded from AI analysis."""
        try:
            result = await db.execute(select(Message).filter(Message.id == message_id))
            message = result.scalar_one_or_none()
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            if message.is_manual_skip:
                message.is_manual_skip = False
                message.analysis_status = "pending"
                message.skip_reason = None
            else:
                message.is_manual_skip = True
                message.analysis_status = "skipped"
                message.skip_reason = "manual"
            await db.commit()

            return {"success": True, "is_manual_skip": message.is_manual_skip, "analysis_status": message.analysis_status}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to toggle skip: {str(e)}")

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
