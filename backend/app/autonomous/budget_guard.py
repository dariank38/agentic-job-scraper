"""Token budget management for Ollama to prevent runaway LLM usage."""

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AutonomousState

logger = logging.getLogger(__name__)


@dataclass
class BudgetSnapshot:
    """In-memory snapshot of daily token usage."""

    day: date
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OllamaBudgetGuard:
    """Tracks and enforces a daily token budget for Ollama calls.

    Persists usage to the database so restarts do not reset the counter.
    Designed to prevent the autonomous self-learning loop from exhausting
    system resources.
    """

    def __init__(
        self,
        db: AsyncSession,
        daily_token_limit: Optional[int] = None,
        state_key: str = "ollama_budget",
    ):
        self.db = db
        self.daily_token_limit = max(
            daily_token_limit or int(os.getenv("AUTONOMOUS_OLLAMA_BUDGET", "100000")),
            1,
        )
        self.state_key = state_key
        self._snapshot: Optional[BudgetSnapshot] = None

    async def initialize(self) -> None:
        """Load today's usage from persistent state."""
        today = date.today()
        state = await self._load_state()
        if state and state.get("day") == today.isoformat():
            self._snapshot = BudgetSnapshot(
                day=today,
                prompt_tokens=state.get("prompt_tokens", 0),
                completion_tokens=state.get("completion_tokens", 0),
                total_tokens=state.get("total_tokens", 0),
            )
        else:
            self._snapshot = BudgetSnapshot(day=today)

    async def check(self, estimated_tokens: int) -> bool:
        """Return True if the request fits within the daily budget."""
        if self._snapshot is None:
            await self.initialize()

        if self._snapshot.day != date.today():
            await self._rollover()

        projected = self._snapshot.total_tokens + estimated_tokens
        if projected > self.daily_token_limit:
            logger.warning(
                "Ollama budget guard: projected usage %s exceeds daily limit %s",
                projected,
                self.daily_token_limit,
            )
            return False

        return True

    async def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Record actual token usage after an LLM call."""
        if self._snapshot is None:
            await self.initialize()

        if self._snapshot.day != date.today():
            await self._rollover()

        self._snapshot.prompt_tokens += prompt_tokens
        self._snapshot.completion_tokens += completion_tokens
        self._snapshot.total_tokens += prompt_tokens + completion_tokens
        await self._persist_state()

    async def _rollover(self) -> None:
        """Reset the snapshot when the day changes."""
        self._snapshot = BudgetSnapshot(day=date.today())
        await self._persist_state()

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate for English/Chinese mixed text."""
        if not text:
            return 0
        # Chinese characters are roughly 1 token each; English words ~1.3 tokens
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_tokens = int(len(text.split()) * 1.3)
        return chinese_chars + other_tokens

    async def _load_state(self) -> Optional[dict]:
        result = await self.db.execute(
            select(AutonomousState).filter(AutonomousState.key == self.state_key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def _persist_state(self) -> None:
        if self._snapshot is None:
            return

        value = {
            "day": self._snapshot.day.isoformat(),
            "prompt_tokens": self._snapshot.prompt_tokens,
            "completion_tokens": self._snapshot.completion_tokens,
            "total_tokens": self._snapshot.total_tokens,
        }
        result = await self.db.execute(
            select(AutonomousState).filter(AutonomousState.key == self.state_key)
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            row = AutonomousState(key=self.state_key, value=value)
            self.db.add(row)
        await self.db.commit()
