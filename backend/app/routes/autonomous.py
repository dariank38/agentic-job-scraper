"""API routes for autonomous system dashboard."""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal
from app.models import AutonomousState, Channel, FetchOutcome, SourceScoring, WebsiteSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])


@router.get("/status")
async def get_autonomous_status():
    """Get overall autonomous system status."""
    async with AsyncSessionLocal() as db:
        # Check if autonomous mode is enabled
        import os
        enabled = os.getenv("ENABLE_AUTONOMOUS_MODE", "false").lower() == "true"

        # Get budget state
        budget_state = await db.execute(
            select(AutonomousState).filter(AutonomousState.key == "ollama_budget")
        )
        budget_row = budget_state.scalar_one_or_none()
        budget = budget_row.value if budget_row else {}

        # Count sources with scorings
        scoring_count = await db.execute(select(func.count(SourceScoring.source_id)))
        total_scored = scoring_count.scalar() or 0

        # Count recent fetch outcomes
        since = datetime.utcnow() - timedelta(hours=24)
        recent_outcomes = await db.execute(
            select(func.count(FetchOutcome.id)).filter(FetchOutcome.fetched_at >= since)
        )
        total_fetches = recent_outcomes.scalar() or 0

        # Count recent failures
        recent_failures = await db.execute(
            select(func.count(FetchOutcome.id)).filter(
                FetchOutcome.fetched_at >= since,
                FetchOutcome.error_type.isnot(None),
            )
        )
        total_failures = recent_failures.scalar() or 0

        return {
            "enabled": enabled,
            "budget": budget,
            "sources_scored": total_scored,
            "fetches_24h": total_fetches,
            "failures_24h": total_failures,
        }


@router.get("/sources")
async def get_source_scorings():
    """Get all source scorings with interval recommendations."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SourceScoring))
        scorings = result.scalars().all()

        # Enrich with source names
        enriched = []
        for scoring in scorings:
            if scoring.source_type == "telegram":
                channel = await db.execute(
                    select(Channel).filter(Channel.id == scoring.source_id)
                )
                channel_row = channel.scalar_one_or_none()
                name = channel_row.username or channel_row.name if channel_row else f"Channel {scoring.source_id}"
            else:
                source = await db.execute(
                    select(WebsiteSource).filter(WebsiteSource.id == scoring.source_id)
                )
                source_row = source.scalar_one_or_none()
                name = source_row.name if source_row else f"Website {scoring.source_id}"

            enriched.append({
                "source_id": scoring.source_id,
                "source_type": scoring.source_type,
                "name": name,
                "hourly_yield_24h": scoring.hourly_yield_24h,
                "hourly_yield_7d": scoring.hourly_yield_7d,
                "best_window_start": scoring.best_window_start,
                "best_window_end": scoring.best_window_end,
                "recommended_interval_minutes": scoring.recommended_interval_minutes,
                "consecutive_failures": scoring.consecutive_failures,
                "last_optimized_at": scoring.last_optimized_at.isoformat() if scoring.last_optimized_at else None,
            })

        return enriched


@router.get("/outcomes")
async def get_fetch_outcomes(limit: int = 50):
    """Get recent fetch outcomes."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FetchOutcome)
            .order_by(FetchOutcome.fetched_at.desc())
            .limit(limit)
        )
        outcomes = result.scalars().all()

        return [
            {
                "id": o.id,
                "source_id": o.source_id,
                "source_type": o.source_type,
                "fetched_at": o.fetched_at.isoformat(),
                "new_jobs_found": o.new_jobs_found,
                "new_messages": o.new_messages,
                "duration_seconds": o.duration_seconds,
                "error_type": o.error_type,
                "error_message": o.error_message,
            }
            for o in outcomes
        ]


@router.get("/state")
async def get_autonomous_state():
    """Get all autonomous state key-values."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AutonomousState))
        states = result.scalars().all()

        return {
            s.key: {
                "value": s.value,
                "updated_at": s.updated_at.isoformat(),
            }
            for s in states
        }


@router.get("/discovered")
async def get_discovered_sources():
    """Get inactive sources (candidates from discovery)."""
    async with AsyncSessionLocal() as db:
        # Inactive channels
        channels = await db.execute(
            select(Channel).filter(Channel.is_active == False)
        )
        inactive_channels = channels.scalars().all()

        # Inactive website sources
        websites = await db.execute(
            select(WebsiteSource).filter(WebsiteSource.is_active == False)
        )
        inactive_websites = websites.scalars().all()

        return {
            "channels": [
                {
                    "id": c.id,
                    "username": c.username,
                    "name": c.name,
                    "description": c.description,
                    "created_at": c.created_at.isoformat(),
                }
                for c in inactive_channels
            ],
            "websites": [
                {
                    "id": w.id,
                    "name": w.name,
                    "url": w.url,
                    "site_type": w.site_type,
                    "extraction_prompt": w.extraction_prompt,
                    "created_at": w.created_at.isoformat(),
                }
                for w in inactive_websites
            ],
        }


def register_autonomous_routes(app):
    """Register autonomous routes to the FastAPI app."""
    app.include_router(router)
