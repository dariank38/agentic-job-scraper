"""Publish analyzed jobs from the scraper to the Jobees platform."""

import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal
from app.models import Job

logger = logging.getLogger(__name__)

JOBEES_API_URL = os.getenv("JOBEES_API_URL", "http://localhost:8001")
JOBEES_API_KEY = os.getenv("JOBEES_API_KEY", "")

# Default values aligned with Jobees schema
DEFAULT_CATEGORY = "其他"
DEFAULT_PRIORITY = "P2"
DEFAULT_SALARY_LEVEL = "negotiable"


JOBEES_CATEGORIES = {
    "运营", "增长", "技术", "产品", "AI专项", "设计", "内容", "职能", "客服", "其他"
}


def _normalize_category(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_CATEGORY
    value = str(value).strip()
    return value if value in JOBEES_CATEGORIES else DEFAULT_CATEGORY


def _normalize_priority(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_PRIORITY
    value = str(value).strip().upper()
    return value if value in {"P0", "P1", "P2"} else DEFAULT_PRIORITY


def _normalize_salary_level(value: Optional[str]) -> str:
    if not value:
        return DEFAULT_SALARY_LEVEL
    value = str(value).strip().lower()
    return value if value in {"high", "normal", "negotiable"} else DEFAULT_SALARY_LEVEL


def _strip_contact_lines(jd: str) -> str:
    """Remove trailing contact/channel/hashtag lines from JD."""
    import re
    lines = jd.split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if re.match(r"^(联系\s*HR|联系方式|招聘频道)[：:]", last):
            lines.pop()
            continue
        if re.match(r"^@\w+\s*$", last):
            lines.pop()
            continue
        if re.match(r"^(#\w+\s*)+$", last):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()


def _build_jobees_payload(job: Job) -> dict:
    """Map a scraper Job to a Jobees JobCreate payload."""
    jd = _strip_contact_lines(job.jd) if job.jd else ""
    if not jd:
        jd = job.title or "No description"

    return {
        "title": (job.title or "Untitled").strip()[:255],
        "salary": (job.salary or "面议").strip()[:120],
        "salary_level": _normalize_salary_level(job.salary_level),
        "location": (job.location or "远程").strip()[:120],
        "is_remote": bool(job.is_remote) if job.is_remote is not None else True,
        "category": _normalize_category(job.category),
        "priority": _normalize_priority(job.priority),
        "jd": jd,
        "hr_contact": (job.hr_contact or "").strip()[:120],
        "channel_contact": (job.channel_contact or job.channel_name or "").strip()[:120],
        "is_published": True,
    }


async def publish_jobs(job_ids: Optional[list[int]] = None) -> dict:
    """Publish scraper jobs to Jobees.

    Args:
        job_ids: Optional list of specific job IDs to publish. If None, publishes
            all jobs where published_to_jobees is False and is_hidden is False.

    Returns:
        Summary dict with created, skipped, failed, published.
    """
    if not JOBEES_API_URL or not JOBEES_API_KEY:
        logger.warning("[JOBEES] Publisher not configured; set JOBEES_API_URL and JOBEES_API_KEY")
        return {"published": 0, "created": 0, "skipped": 0, "failed": 0, "errors": ["JOBEES_API_URL or JOBEES_API_KEY not set"]}

    async with AsyncSessionLocal() as db:
        try:
            query = select(Job).filter(
                Job.published_to_jobees == False,
                Job.is_hidden == False,
                Job.title.isnot(None),
            )
            if job_ids:
                query = query.filter(Job.id.in_(job_ids))
            result = await db.execute(query)
            jobs = result.scalars().all()

            if not jobs:
                return {"published": 0, "created": 0, "skipped": 0, "failed": 0, "errors": []}

            payloads = [_build_jobees_payload(job) for job in jobs]
            logger.info(f"[JOBEES] Publishing {len(payloads)} jobs to {JOBEES_API_URL}/api/external/jobs/bulk")
            for job in jobs:
                logger.info(f"[JOBEES]   → job_id={job.id} | title={job.title[:80]} | category={_normalize_category(job.category)} | salary={job.salary or 'N/A'}")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{JOBEES_API_URL}/api/external/jobs/bulk",
                    headers={"X-API-Key": JOBEES_API_KEY, "Content-Type": "application/json"},
                    json={"jobs": payloads},
                )
                response.raise_for_status()
                data = response.json()

            created = int(data.get("created", 0))
            skipped = int(data.get("skipped", 0))
            failed = int(data.get("failed", 0))
            errors = data.get("errors", []) or []

            # Mark all attempted jobs as published so we don't retry the same batch forever.
            # The Jobees endpoint deduplicates; skipped means already present.
            now = datetime.utcnow()
            for job in jobs:
                job.published_to_jobees = True
                job.published_at = now

            await db.commit()
            logger.info(f"[JOBEES] ✓ Done: created={created} skipped={skipped} failed={failed}")
            if errors:
                for err in errors:
                    logger.warning(f"[JOBEES]   ⚠ {err}")
            return {"published": len(jobs), "created": created, "skipped": skipped, "failed": failed, "errors": errors}

        except httpx.HTTPStatusError as e:
            logger.error(f"[JOBEES] HTTP error {e.response.status_code}: {e.response.text[:200]}")
            return {"published": 0, "created": 0, "skipped": 0, "failed": 0, "errors": [f"HTTP {e.response.status_code}: {e.response.text[:200]}"]}
        except Exception as e:
            logger.error(f"[JOBEES] Publish error: {e}", exc_info=True)
            return {"published": 0, "created": 0, "skipped": 0, "failed": 0, "errors": [str(e)]}


async def publish_single_job(job_id: int) -> dict:
    """Publish a single job by ID."""
    return await publish_jobs(job_ids=[job_id])
