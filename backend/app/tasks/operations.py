"""Operation records and WebSocket broadcast helpers."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal, manager
from app.models import Channel, Operation

logger = logging.getLogger(__name__)


async def broadcast_progress(event_type: str, data: dict):
    try:
        await manager.broadcast({"type": event_type, **data})
    except Exception:
        pass


async def broadcast_stats_update(db: AsyncSession):
    try:
        from sqlalchemy import func
        from app.models import Channel, Job, Developer, Message

        total_channels = (await db.execute(select(func.count()).select_from(Channel))).scalar()
        job_postings = (await db.execute(select(func.count()).select_from(Job))).scalar()
        developers = (await db.execute(select(func.count()).select_from(Developer))).scalar()
        total_messages = (await db.execute(select(func.count()).select_from(Message))).scalar()
        analyzed_messages = (await db.execute(select(func.count()).select_from(Message).filter(Message.analysis_status == 'analyzed'))).scalar()
        pending_messages = (await db.execute(select(func.count()).select_from(Message).filter(Message.analysis_status == 'pending'))).scalar()
        skipped_messages = (await db.execute(select(func.count()).select_from(Message).filter(Message.analysis_status == 'skipped'))).scalar()

        await broadcast_progress("stats_update", {
            "total_channels": total_channels,
            "job_postings": job_postings,
            "developers": developers,
            "total_messages": total_messages,
            "analyzed_messages": analyzed_messages,
            "pending_messages": pending_messages,
            "skipped_messages": skipped_messages,
            "applications": {"jobs": {"total": 0}},
            "ollama_available": True,
        })
    except Exception as e:
        logger.error(f"Error broadcasting stats update: {e}")


async def create_operation(
    db: AsyncSession,
    operation_type: str,
    channel: Optional[Channel],
    total_messages: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> int:
    operation = Operation(
        operation_type=operation_type,
        channel_id=channel.id if channel else None,
        channel_username=channel.username if channel else None,
        bulk_operation_id=bulk_operation_id,
        status="running",
        total_messages=total_messages or 0,
    )
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    return operation.id


async def update_operation(
    db: AsyncSession,
    operation_id: int,
    status: Optional[str] = None,
    current: Optional[int] = None,
    total: Optional[int] = None,
    total_messages: Optional[int] = None,
    analyzed: Optional[int] = None,
    jobs_found: Optional[int] = None,
    developers_found: Optional[int] = None,
    error_message: Optional[str] = None,
    channel_username: Optional[str] = None,
    commit: bool = True,
):
    result = await db.execute(select(Operation).filter(Operation.id == operation_id))
    operation = result.scalar_one_or_none()
    if not operation:
        return
    if status is not None:
        operation.status = status
    if current is not None:
        operation.current = current
    if total is not None:
        operation.total = total
    if total_messages is not None:
        operation.total_messages = total_messages
    if analyzed is not None:
        operation.analyzed = analyzed
    if jobs_found is not None:
        operation.jobs_found = jobs_found
    if channel_username is not None:
        operation.channel_username = channel_username
    if developers_found is not None:
        operation.developers_found = developers_found
    if error_message is not None:
        operation.error_message = error_message
    if status in ("completed", "stopped", "error"):
        operation.completed_at = datetime.utcnow()
    if commit:
        await db.commit()


async def cleanup_stale_operations():
    """Mark stale 'running' operations as 'stopped' on backend startup."""
    from app.tasks.stop_events import analysis_stop_events, bulk_stop_events
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Operation).filter(Operation.status == "running"))
            stale_ops = result.scalars().all()
            if not stale_ops:
                return
            stale_count = 0
            for op in stale_ops:
                is_stale = False
                if op.started_at:
                    age = datetime.now(timezone.utc) - op.started_at.replace(tzinfo=timezone.utc)
                    if age > timedelta(hours=1):
                        is_stale = True
                if op.channel_id and op.channel_id not in analysis_stop_events:
                    is_stale = True
                if op.bulk_operation_id and op.bulk_operation_id not in bulk_stop_events:
                    is_stale = True
                if is_stale:
                    op.status = "stopped"
                    stale_count += 1
            if stale_count > 0:
                await db.commit()
        except Exception as e:
            await db.rollback()
