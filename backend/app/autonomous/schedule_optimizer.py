"""Dynamic schedule optimization based on historical source yield."""

import logging
from datetime import datetime, timedelta, time
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.autonomous.budget_guard import OllamaBudgetGuard
from app.autonomous.state_manager import AutonomousStateManager
from app.models import Channel, FetchOutcome, SourceScoring, WebsiteSource
from services.ollama_service import AsyncOllamaAnalyzer

logger = logging.getLogger(__name__)


class ScheduleOptimizer:
    """Analyze fetch history and optimize APScheduler intervals.

    Rules (independent of LLM):
        - Minimum interval: 10 minutes
        - Maximum interval: 12 hours
        - Double interval after 3 consecutive failures
        - Default interval: 60 minutes

    LLM is used optionally to suggest a refined interval with reasoning.
    """

    MIN_INTERVAL = 10
    MAX_INTERVAL = 12 * 60  # 720 minutes
    DEFAULT_INTERVAL = 60
    FAILURE_THRESHOLD = 3

    def __init__(
        self,
        db: AsyncSession,
        analyzer: Optional[AsyncOllamaAnalyzer] = None,
        budget_guard: Optional[OllamaBudgetGuard] = None,
    ):
        self.db = db
        self.analyzer = analyzer
        self.budget_guard = budget_guard

    async def optimize_all(self) -> list[SourceScoring]:
        """Run optimization for all active sources and return updates."""
        website_sources = await self.db.execute(
            select(WebsiteSource).filter(WebsiteSource.is_active == True)
        )
        telegram_channels = await self.db.execute(
            select(Channel).filter(Channel.is_active == True)
        )

        updates: list[SourceScoring] = []
        for source in website_sources.scalars():
            scoring = await self._optimize_source(source.id, "website", source.name)
            if scoring:
                updates.append(scoring)

        for channel in telegram_channels.scalars():
            scoring = await self._optimize_source(channel.id, "telegram", channel.username or channel.name)
            if scoring:
                updates.append(scoring)

        return updates

    async def _optimize_source(
        self, source_id: int, source_type: str, source_name: str
    ) -> Optional[SourceScoring]:
        result = await self.db.execute(
            select(SourceScoring).filter(
                SourceScoring.source_id == source_id,
                SourceScoring.source_type == source_type,
            )
        )
        scoring = result.scalar_one_or_none()
        if not scoring:
            scoring = SourceScoring(
                source_id=source_id,
                source_type=source_type,
                recommended_interval_minutes=self.DEFAULT_INTERVAL,
            )
            self.db.add(scoring)

        # Compute yields
        now = datetime.utcnow()
        yield_24h = await self._compute_yield(source_id, source_type, now - timedelta(hours=24))
        yield_7d = await self._compute_yield(source_id, source_type, now - timedelta(days=7))
        failures = await self._count_failures(source_id, source_type, now - timedelta(days=7))
        window = await self._compute_best_window(source_id, source_type)

        scoring.hourly_yield_24h = yield_24h
        scoring.hourly_yield_7d = yield_7d
        scoring.consecutive_failures = failures
        scoring.best_window_start = window["start"]
        scoring.best_window_end = window["end"]
        scoring.last_optimized_at = now

        # Base interval from yield
        if failures >= self.FAILURE_THRESHOLD:
            interval = min(scoring.recommended_interval_minutes * 2, self.MAX_INTERVAL)
        elif yield_7d <= 0:
            interval = self.MAX_INTERVAL
        elif yield_24h >= 5:
            interval = self.MIN_INTERVAL
        elif yield_24h >= 1:
            interval = 30
        else:
            interval = self.DEFAULT_INTERVAL

        # Optional LLM refinement
        if self.analyzer and self.budget_guard:
            llm_interval = await self._llm_recommend_interval(
                source_name, source_type, yield_24h, yield_7d, failures, window
            )
            if llm_interval:
                interval = llm_interval

        scoring.recommended_interval_minutes = max(
            self.MIN_INTERVAL, min(self.MAX_INTERVAL, interval)
        )

        await self.db.commit()
        logger.info(
            "[SCHEDULE OPTIMIZER] %s id=%s interval=%dmin 24h_yield=%d 7d_yield=%d failures=%d",
            source_type,
            source_id,
            scoring.recommended_interval_minutes,
            yield_24h,
            yield_7d,
            failures,
        )
        return scoring

    async def _compute_yield(
        self, source_id: int, source_type: str, since: datetime
    ) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(FetchOutcome.new_jobs_found), 0)).filter(
                FetchOutcome.source_id == source_id,
                FetchOutcome.source_type == source_type,
                FetchOutcome.fetched_at >= since,
                FetchOutcome.error_type.is_(None),
            )
        )
        total_jobs = result.scalar() or 0
        hours = max(1, (datetime.utcnow() - since).total_seconds() / 3600)
        return int(total_jobs / hours)

    async def _count_failures(
        self, source_id: int, source_type: str, since: datetime
    ) -> int:
        result = await self.db.execute(
            select(func.count(FetchOutcome.id)).filter(
                FetchOutcome.source_id == source_id,
                FetchOutcome.source_type == source_type,
                FetchOutcome.fetched_at >= since,
                FetchOutcome.error_type.isnot(None),
            )
        )
        return result.scalar() or 0

    async def _compute_best_window(
        self, source_id: int, source_type: str
    ) -> dict[str, Optional[str]]:
        """Find the hour of day with the highest yield in the last 7 days."""
        since = datetime.utcnow() - timedelta(days=7)
        result = await self.db.execute(
            select(
                func.extract("hour", FetchOutcome.fetched_at).label("hour"),
                func.sum(FetchOutcome.new_jobs_found).label("jobs"),
            )
            .filter(
                FetchOutcome.source_id == source_id,
                FetchOutcome.source_type == source_type,
                FetchOutcome.fetched_at >= since,
                FetchOutcome.error_type.is_(None),
            )
            .group_by("hour")
            .order_by(func.sum(FetchOutcome.new_jobs_found).desc())
            .limit(1)
        )
        row = result.first()
        if row and row.jobs:
            best_hour = int(row.hour)
            start = time(best_hour, 0)
            end = time((best_hour + 3) % 24, 0)
            return {
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
            }
        return {"start": None, "end": None}

    async def _llm_recommend_interval(
        self,
        source_name: str,
        source_type: str,
        yield_24h: int,
        yield_7d: int,
        failures: int,
        window: dict,
    ) -> Optional[int]:
        """Optionally ask LLM for an interval recommendation."""
        if not self.analyzer or not self.budget_guard:
            return None

        prompt = f"""You are optimizing a job scraper schedule.

Source: {source_name} ({source_type})
Jobs per hour (24h): {yield_24h}
Jobs per hour (7d): {yield_7d}
Consecutive failures: {failures}
Best historical window: {window['start']} to {window['end']}

Recommend a fetch interval in minutes between 10 and 720.
Return only a JSON object: {{"interval_minutes": int, "reason": str}}
"""
        estimated = self.budget_guard.estimate_tokens(prompt)
        if not await self.budget_guard.check(estimated):
            return None

        try:
            result = await self.analyzer.analyze_message(prompt)
            await self.budget_guard.record_usage(
                prompt_tokens=estimated,
                completion_tokens=self.budget_guard.estimate_tokens(str(result)),
            )
            if isinstance(result, dict) and "interval_minutes" in result:
                return int(result["interval_minutes"])
        except Exception as e:
            logger.warning("[SCHEDULE OPTIMIZER] LLM recommendation failed: %s", e)

        return None
