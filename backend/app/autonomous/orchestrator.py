"""Central autonomous orchestrator for the job scraper."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.autonomous.budget_guard import OllamaBudgetGuard
from app.autonomous.schedule_optimizer import ScheduleOptimizer
from app.autonomous.self_healing_scraper import SelfHealingScraper
from app.autonomous.source_discovery import SourceDiscoveryAgent
from app.autonomous.state_manager import AutonomousStateManager
from app.connection import AsyncSessionLocal
from app.models import FetchOutcome
from services.ollama_service import AsyncOllamaAnalyzer

logger = logging.getLogger(__name__)


class AutonomousOrchestrator:
    """Central control loop that runs the autonomous agent layers.

    Responsibilities:
        1. Optimize scraping schedules daily based on historical yield.
        2. Discover new sources weekly.
        3. Record fetch outcomes for learning.
        4. Enforce Ollama token budget.

    The orchestrator is additive: it does not replace manual UI controls.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.analyzer = AsyncOllamaAnalyzer()
        self.running = False
        self._db: AsyncSession | None = None

    async def _get_db(self) -> AsyncSession:
        if self._db is None:
            self._db = AsyncSessionLocal()
        return self._db

    async def start(self) -> None:
        if not os.getenv("ENABLE_AUTONOMOUS_MODE", "false").lower() == "true":
            logger.info("[AUTONOMOUS] Autonomous mode disabled. Set ENABLE_AUTONOMOUS_MODE=true to enable.")
            return

        self.running = True
        db = await self._get_db()
        state_manager = AutonomousStateManager(db)
        budget_guard = OllamaBudgetGuard(db)
        await budget_guard.initialize()

        self.scheduler.add_job(
            self._run_schedule_optimizer,
            "cron",
            hour=3,
            minute=0,
            id="autonomous_schedule_optimizer",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_source_discovery,
            "cron",
            day_of_week="sun",
            hour=2,
            minute=0,
            id="autonomous_source_discovery",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_health_check,
            "interval",
            minutes=30,
            id="autonomous_health_check",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("[AUTONOMOUS] Orchestrator started")

        while self.running:
            await asyncio.sleep(60)

    async def stop(self) -> None:
        self.running = False
        self.scheduler.shutdown(wait=False)
        if self._db:
            await self._db.close()
        logger.info("[AUTONOMOUS] Orchestrator stopped")

    async def _run_schedule_optimizer(self) -> None:
        async with AsyncSessionLocal() as db:
            optimizer = ScheduleOptimizer(db, self.analyzer)
            await optimizer.optimize_all()

    async def _run_source_discovery(self) -> None:
        async with AsyncSessionLocal() as db:
            budget_guard = OllamaBudgetGuard(db)
            await budget_guard.initialize()
            scraper = SelfHealingScraper(self.analyzer, budget_guard)
            agent = SourceDiscoveryAgent(db, self.analyzer, budget_guard, scraper)
            await agent.scout()

    async def _run_health_check(self) -> None:
        async with AsyncSessionLocal() as db:
            recent_failures = await self._count_recent_failures(db)
            logger.info("[AUTONOMOUS HEALTH] Recent fetch failures: %d", recent_failures)

    async def record_fetch_outcome(
        self,
        source_id: int,
        source_type: str,
        new_jobs: int,
        new_messages: int,
        duration_seconds: int,
        error: Optional[Exception] = None,
    ) -> None:
        """Record a fetch outcome for learning. Public so fetch tasks can call it."""
        async with AsyncSessionLocal() as db:
            outcome = FetchOutcome(
                source_id=source_id,
                source_type=source_type,
                new_jobs_found=new_jobs,
                new_messages=new_messages,
                duration_seconds=duration_seconds,
                error_type=type(error).__name__ if error else None,
                error_message=str(error) if error else None,
                fetched_at=datetime.utcnow(),
            )
            db.add(outcome)
            await db.commit()

    async def _count_recent_failures(self, db: AsyncSession) -> int:
        from datetime import timedelta
        from sqlalchemy import func, select
        from app.models import FetchOutcome

        since = datetime.utcnow() - timedelta(hours=24)
        result = await db.execute(
            select(func.count(FetchOutcome.id)).filter(
                FetchOutcome.fetched_at >= since,
                FetchOutcome.error_type.isnot(None),
            )
        )
        return result.scalar() or 0
