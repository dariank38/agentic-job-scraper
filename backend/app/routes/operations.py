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
        from datetime import datetime, timedelta
        # Get running, error, and recently stopped operations (within last 5 minutes)
        recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
        # Force fresh data from database (not cached)
        db.expire_all()
        result = await db.execute(
            select(Operation)
            .filter(
                (Operation.status.in_(["running", "error"])) |
                ((Operation.status == "stopped") & (Operation.completed_at >= recent_cutoff))
            )
            .order_by(Operation.started_at.desc())
            .limit(20)
        )
        operations = result.scalars().all()

        # Get unique bulk operation IDs from RUNNING operations only
        bulk_operations = {}
        for op in operations:
            if op.bulk_operation_id and op.status == "running":
                if op.bulk_operation_id not in bulk_operations:
                    bulk_operations[op.bulk_operation_id] = {
                        "id": op.bulk_operation_id,
                        "operation_type": "bulk-analyze" if "analyze-all" in op.bulk_operation_id else "bulk-fetch-analyze",
                        "status": "running",
                        "channels": [],
                    }
                bulk_operations[op.bulk_operation_id]["channels"].append(op.channel_id)

        return {
            "operations": [
                {
                    "id": op.id,
                    "operation_type": op.operation_type,
                    "channel_id": op.channel_id,
                    "channel_username": op.channel_username,
                    "bulk_operation_id": op.bulk_operation_id,
                    "status": op.status,
                    "current": op.current,
                    "total": op.total,
                    "total_messages": op.total_messages,
                    "analyzed": op.analyzed,
                    "jobs_found": op.jobs_found,
                    "developers_found": op.developers_found,
                    "error_message": op.error_message,
                    "started_at": op.started_at.isoformat() if op.started_at else None,
                    "completed_at": op.completed_at.isoformat() if op.completed_at else None,
                }
                for op in operations
            ],
            "bulk_operations": list(bulk_operations.values()),
        }

    @app.get("/api/operations/all")
    async def get_all_operations(db: AsyncSession = Depends(get_db)):
        """Get ALL operations (including completed) for debugging."""
        result = await db.execute(
            select(Operation)
            .order_by(Operation.started_at.desc())
            .limit(50)
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
                    "started_at": op.started_at.isoformat() if op.started_at else None,
                    "completed_at": op.completed_at.isoformat() if op.completed_at else None,
                }
                for op in operations
            ],
            "summary": {
                "running": len([o for o in operations if o.status == "running"]),
                "completed": len([o for o in operations if o.status == "completed"]),
                "stopped": len([o for o in operations if o.status == "stopped"]),
                "error": len([o for o in operations if o.status == "error"]),
            }
        }

    @app.post("/api/operations/cleanup")
    async def cleanup_stuck_operations(db: AsyncSession = Depends(get_db)):
        """Mark old 'running' operations as 'error' - use when backend restarted."""
        from datetime import datetime, timedelta
        import logging
        logger = logging.getLogger(__name__)
        
        # Find operations running for more than 10 minutes
        stale_cutoff = datetime.utcnow() - timedelta(minutes=10)
        result = await db.execute(
            select(Operation).filter(
                (Operation.status == "running") &
                (Operation.started_at < stale_cutoff)
            )
        )
        stuck_ops = result.scalars().all()
        
        fixed_count = 0
        for op in stuck_ops:
            op.status = "error"
            op.error_message = "Marked as error - backend restart detected"
            op.completed_at = datetime.utcnow()
            fixed_count += 1
            logger.info(f"[CLEANUP] Fixed stuck operation {op.id} for channel {op.channel_username}")
        
        await db.commit()
        return {"fixed": fixed_count, "operations": [op.id for op in stuck_ops]}

    @app.get("/api/operations/current-analyzing")
    async def get_current_analyzing(db: AsyncSession = Depends(get_db)):
        """Get current analyzing messages for all running operations."""
        from datetime import datetime, timedelta
        # Get running operations from the last 10 minutes
        recent_cutoff = datetime.utcnow() - timedelta(minutes=10)
        db.expire_all()
        result = await db.execute(
            select(Operation).filter(
                (Operation.status == "running") &
                (Operation.started_at >= recent_cutoff)
            )
        )
        operations = result.scalars().all()

        # Return minimal info for running operations
        return {
            "operations": [
                {
                    "channel_username": op.channel_username,
                    "status": op.status,
                    "analyzed": op.analyzed,
                    "total": op.total,
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
            "total_messages": operation.total_messages,
            "analyzed": operation.analyzed,
            "jobs_found": operation.jobs_found,
            "developers_found": operation.developers_found,
            "error_message": operation.error_message,
            "started_at": operation.started_at.isoformat() if operation.started_at else None,
            "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
        }
