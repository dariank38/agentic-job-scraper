"""Persistent state management for autonomous learned behavior."""

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AutonomousState

logger = logging.getLogger(__name__)


class AutonomousStateManager:
    """Read/write dynamic, learned state to PostgreSQL.

    This manager abstracts the `autonomous_states` table so that the agent can
    remember scheduling patterns, healed selectors, fingerprint rotation
    indices, and budget data across process restarts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Load a state value by key."""
        result = await self.db.execute(
            select(AutonomousState).filter(AutonomousState.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else default

    async def set(self, key: str, value: Any) -> None:
        """Persist a state value by key."""
        result = await self.db.execute(
            select(AutonomousState).filter(AutonomousState.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            row = AutonomousState(key=key, value=value)
            self.db.add(row)
        await self.db.commit()
        logger.info("[AUTONOMOUS STATE] Persisted state for key: %s", key)

    async def merge(self, key: str, value: dict) -> dict:
        """Merge a dict into an existing state value."""
        existing = await self.get(key, default={})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(value)
        await self.set(key, existing)
        return existing

    async def delete(self, key: str) -> None:
        """Delete a state value."""
        result = await self.db.execute(
            select(AutonomousState).filter(AutonomousState.key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            await self.db.delete(row)
            await self.db.commit()
