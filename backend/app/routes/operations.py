"""Operations-related API routes for state management."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db
from app.models import Operation


def register_operations_routes(app):
    """Register operations-related routes."""

    @app.get("/api/operations")
    async def get_operations(db: AsyncSession = Depends(get_db)):
        """Get all running and recent operations."""
        result = await db.execute(
            select(Operation)
            .filter(Operation.status.in_(["running", "error"]))
            .order_by(Operation.started_at.desc())
            .limit(20)
        )
        operations = result.scalars().all()

        return {
            "operations": [
                {
                    "id": op.id,
                    "operation_type": op.operation_type,
                    "channel_id": op.channel_id,
                    "channel_username": op.channel_username,
                    "status": op.status,
                    "current": op.current,
                    "total": op.total,
                    "analyzed": op.analyzed,
                    "jobs_found": op.jobs_found,
                    "developers_found": op.developers_found,
                    "error_message": op.error_message,
                    "started_at": op.started_at.isoformat() if op.started_at else None,
                    "completed_at": op.completed_at.isoformat() if op.completed_at else None,
                }
                for op in operations
            ]
        }

    @app.get("/api/operations/{operation_id}")
    async def get_operation(operation_id: int, db: AsyncSession = Depends(get_db)):
        """Get a specific operation by ID."""
        result = await db.execute(select(Operation).filter(Operation.id == operation_id))
        operation = result.scalar_one_or_none()

        if not operation:
            return {"error": "Operation not found"}

        return {
            "id": operation.id,
            "operation_type": operation.operation_type,
            "channel_id": operation.channel_id,
            "channel_username": operation.channel_username,
            "status": operation.status,
            "current": operation.current,
            "total": operation.total,
            "analyzed": operation.analyzed,
            "jobs_found": operation.jobs_found,
            "developers_found": operation.developers_found,
            "error_message": operation.error_message,
            "started_at": operation.started_at.isoformat() if operation.started_at else None,
            "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
        }
