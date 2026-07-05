"""Website source fetch/analyze API routes and background task helpers."""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks, Depends, Form, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db, AsyncSessionLocal
from app.models import Developer, Job, Message, WebsiteSource
from app.tasks import (
    broadcast_progress,
    create_operation,
    update_operation,
    analyze_website_posts,
    stop_website_operation,
    website_stop_events,
)
from services.ollama_service import get_analyzer, is_ollama_available
from web_crawler import Fetcher
from web_crawler.config import DEFAULT_DAYS_BACK

logger = logging.getLogger(__name__)



async def _save_rss_entries(db: AsyncSession, source, rss_entries: list, operation_id: str) -> int:
    """Deduplicate and save RSS entries as Messages. Returns count of new messages."""
    messages_added = 0
    total_entries = len(rss_entries)
    source_id = source.id

    for idx, entry in enumerate(rss_entries):
        if isinstance(entry, dict):
            entry_text = entry.get("text", "")
            url = entry.get("link", "")
            published_str = entry.get("published")
            published_date = None
            if published_str:
                try:
                    parsed_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    published_date = parsed_date.replace(tzinfo=None)
                except Exception:
                    pass
        else:
            entry_text = entry
            url = None
            published_date = None
            for line in entry_text.split('\n'):
                if line.startswith('Link:'):
                    url = line.replace('Link:', '').strip()
                elif line.startswith('Published:'):
                    date_str = line.replace('Published:', '').strip()
                    try:
                        parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        published_date = parsed_date.replace(tzinfo=None)
                    except Exception:
                        pass

        post_id = None
        if url and '/t/' in url:
            match = re.search(r'/t/(\d+)', url)
            if match:
                post_id = match.group(1)

        if post_id:
            existing_result = await db.execute(
                select(Message).filter(Message.website_post_id == f"{source_id}-{post_id}")
            )
        else:
            existing_result = await db.execute(select(Message).filter(Message.text == entry_text))
        if existing_result.scalars().first():
            continue

        message = Message(
            website_post_id=f"{source_id}-{post_id}" if post_id else f"{source_id}-{hash(entry_text)}",
            website_source_id=source_id,
            source_type="website",
            text=entry_text,
            analysis_text=entry.get("analysis_text") if isinstance(entry, dict) else None,
            date=published_date,
            sender_username=source.name,
            analysis_status="pending",
        )
        db.add(message)
        await db.flush()
        messages_added += 1

        if messages_added % 5 == 0:
            await broadcast_progress("fetch_progress", {
                "channel": source.name,
                "processed": idx + 1,
                "total": total_entries,
                "operation_id": operation_id,
            })

    return messages_added


async def _fetch_bossjob_bg(source_id: int, operation_id: str, days_back: int):
    """Background task: fetch bossjob.com jobs with Playwright."""
    from web_crawler import fetch_posts

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                logger.warning(f"[BG FETCH BOSSJOB] Source {source_id} not found")
                return

            logger.info(f"[BG FETCH BOSSJOB] Starting fetch for {source.name}")
            await broadcast_progress("fetch_start", {"channel": source.name, "channel_id": source_id, "operation_id": operation_id})

            cookies = None
            if source.cookies:
                try:
                    cookies = json.loads(source.cookies)
                    if not isinstance(cookies, list):
                        cookies = [cookies]
                except json.JSONDecodeError:
                    logger.warning(f"[BG FETCH BOSSJOB] Invalid cookies JSON for source {source_id}")

            analyzer = None
            if await is_ollama_available():
                analyzer = get_analyzer()

            posts = await fetch_posts(
                source.url,
                site_type="bossjob",
                days_back=days_back,
                cookies=cookies,
                analyzer=analyzer,
            )

            if not posts:
                await update_operation(db, operation_id, status="completed")
                await broadcast_progress("fetch_complete", {"channel": source.name, "new_messages": 0, "operation_id": operation_id})
                return

            jobs_added = 0
            for post in posts:
                try:
                    title = post.get("title", "")
                    requirements = post.get("requirements", "")
                    description = post.get("description", "")
                    job_url = post.get("url", "")
                    existing_job = await db.execute(
                        select(Job).filter(Job.website_source_id == source_id, Job.jd.like(f"%{job_url}%"))
                    )
                    if existing_job.scalar_one_or_none():
                        continue
                    db.add(Job(
                        website_source_id=source_id,
                        channel_name=source.name,
                        source_type="website",
                        title=title,
                        company=post.get("company", ""),
                        location=post.get("location", ""),
                        jd=post.get("description", "") + f"\n\nURL: {job_url}",
                        skills=post.get("requirements", ""),
                        channel_contact=job_url,
                        is_applied=False,
                        is_hidden=False,
                    ))
                    jobs_added += 1
                except Exception as e:
                    logger.warning(f"[BG FETCH BOSSJOB] Error saving job: {e}")
                    continue

            await db.commit()
            source.last_fetch_at = datetime.now()
            source.last_fetch_new_count = jobs_added
            await db.commit()

            await update_operation(db, operation_id, status="completed")
            await broadcast_progress("fetch_complete", {"channel": source.name, "new_messages": jobs_added, "operation_id": operation_id})
            logger.info(f"[BG FETCH BOSSJOB] Completed: {jobs_added} new jobs from {source.name}")

        except Exception as e:
            logger.error(f"[BG FETCH BOSSJOB] Error: {e}", exc_info=True)
            try:
                await update_operation(db, operation_id, status="error", error_message=str(e))
            except Exception:
                pass


async def _analyze_website_source_bg(source_id: int):
    """Background task: analyze a single website source with its own DB session."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                logger.warning(f"[BG TASK] Website source {source_id} not found")
                return
            logger.info(f"[BG TASK] Analyzing website source {source.name} (ID: {source_id})")
            analyze_result = await analyze_website_posts(db, source)
            success = analyze_result.get("success", False)
            jobs = analyze_result.get("jobs_found", 0)
            devs = analyze_result.get("developers_found", 0)
            error = analyze_result.get("error", "unknown")
            if success:
                logger.info(f"[BG TASK] Completed analysis for {source.name}: {jobs} jobs, {devs} devs")
            else:
                logger.warning(f"[BG TASK] Analysis failed for {source.name}: {error}")
        except Exception as e:
            logger.error(f"[BG TASK] Exception during analysis for website source {source_id}: {e}", exc_info=True)


async def _run_analyze_websites(source_ids: list, operation_id: str):
    """Background task: analyze multiple website sources sequentially."""
    success_count = error_count = 0
    logger.info(f"[BULK ANALYZE WEBSITES] Starting operation {operation_id} for {len(source_ids)} sources")
    for source_id in source_ids:
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
                source = result.scalar_one_or_none()
                if source:
                    await analyze_website_posts(db, source)
                    success_count += 1
                else:
                    logger.warning(f"[BULK ANALYZE WEBSITES] Source {source_id} not found")
            except Exception as e:
                error_count += 1
                logger.error(f"[BULK ANALYZE WEBSITES] Exception in source {source_id}: {e}", exc_info=True)
    logger.info(f"[BULK ANALYZE WEBSITES] Operation {operation_id} complete: {success_count} success, {error_count} errors")


def register_website_action_routes(app):

    @app.post("/api/website-sources/{source_id}/fetch")
    async def fetch_website_source(
        source_id: int,
        days_back: int = Form(0),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_db),
    ):
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")
            if not source.is_active:
                raise HTTPException(status_code=400, detail="Website source is not active")

            operation_id = await create_operation(db, "fetch", None, total_messages=0)
            await update_operation(db, operation_id, channel_username=source.name)
            await broadcast_progress("fetch_start", {"channel": source.name, "channel_id": source_id, "operation_id": operation_id})

            if source.site_type == "bossjob":
                asyncio.create_task(_fetch_bossjob_bg(source_id, operation_id, days_back or DEFAULT_DAYS_BACK))
                return {"success": True, "message": f"Bossjob fetch started for {source.name} in background", "operation_id": operation_id, "fetch_method": "playwright_async"}

            crawler = Fetcher()
            fetch_result = await crawler.fetch(source.url, days_back=DEFAULT_DAYS_BACK)
            rss_entries = fetch_result["content"]

            if not rss_entries:
                await update_operation(db, operation_id, status="completed")
                await broadcast_progress("fetch_complete", {"channel": source.name, "new_messages": 0, "operation_id": operation_id})
                return {"success": True, "new_messages": 0, "fetch_method": fetch_result["type"], "message": f"No RSS entries found for {source.name}"}

            messages_added = await _save_rss_entries(db, source, rss_entries, operation_id)
            source.last_fetch_new_count = messages_added
            source.last_fetch_at = datetime.utcnow()
            await db.commit()
            await update_operation(db, operation_id, status="completed")
            await broadcast_progress("fetch_complete", {"channel": source.name, "new_messages": messages_added, "operation_id": operation_id})
            return {"success": True, "new_messages": messages_added, "fetch_method": fetch_result["type"], "message": f"Added {messages_added} messages from {source.name}"}

        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"[FETCH WEBSITE] Error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")

    @app.post("/api/website-sources/fetch-all")
    async def fetch_all_website_sources(
        days_back: int = Form(0),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_db),
    ):
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.is_active == True))
            sources = result.scalars().all()
            if not sources:
                return {"success": True, "message": "No active website sources found"}

            total_new = 0
            fetch_methods = []

            for source in sources:
                try:
                    if source.site_type == "bossjob":
                        from web_crawler import fetch_posts
                        analyzer = None
                        if await is_ollama_available():
                            analyzer = get_analyzer()
                        posts = await fetch_posts(source.url, site_type="bossjob", days_back=days_back or DEFAULT_DAYS_BACK, analyzer=analyzer)
                        rss_entries = [{"text": p.get("text", ""), "link": p.get("url", ""), "published": p.get("date").isoformat() if p.get("date") else None} for p in posts]
                        fetch_method = "playwright"
                    else:
                        crawler = Fetcher()
                        fetch_result = await crawler.fetch(source.url, days_back=days_back or DEFAULT_DAYS_BACK)
                        rss_entries = fetch_result["content"]
                        fetch_method = fetch_result["type"]

                    if not rss_entries:
                        continue

                    new_count = 0
                    for entry in rss_entries:
                        entry_text = entry.get("text", "") if isinstance(entry, dict) else entry
                        url = entry.get("link", "") if isinstance(entry, dict) else None
                        published_str = entry.get("published") if isinstance(entry, dict) else None
                        published_date = None
                        if published_str:
                            try:
                                published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00')).replace(tzinfo=None)
                            except Exception:
                                pass

                        post_id = None
                        if url and '/t/' in url:
                            match = re.search(r'/t/(\d+)', url)
                            if match:
                                post_id = match.group(1)

                        if post_id:
                            existing_result = await db.execute(select(Message).filter(Message.website_post_id == f"{source.id}-{post_id}"))
                        else:
                            existing_result = await db.execute(select(Message).filter(Message.text == entry_text))
                        if existing_result.scalars().first():
                            continue

                        db.add(Message(
                            website_post_id=f"{source.id}-{post_id}" if post_id else f"{source.id}-{hash(entry_text)}",
                            website_source_id=source.id,
                            source_type="website",
                            text=entry_text,
                            date=published_date,
                            sender_username=source.name,
                            analysis_status="pending",
                        ))
                        await db.flush()
                        new_count += 1

                    source.last_fetch_new_count = new_count
                    source.last_fetch_at = func.now()
                    total_new += new_count
                    fetch_methods.append(fetch_method)

                except Exception as e:
                    logger.error(f"[WEBSITE SOURCE] Error fetching from {source.name}: {e}", exc_info=True)
                    continue

            await db.commit()
            return {"success": True, "new_messages": total_new, "sources_fetched": len(sources), "fetch_methods": fetch_methods, "message": f"Fetched {total_new} new messages from {len(sources)} source(s)"}

        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error fetching all sources: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/{source_id}/analyze")
    async def analyze_website_source(source_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")
            if not source.is_active:
                raise HTTPException(status_code=400, detail="Website source is not active")
            asyncio.create_task(_analyze_website_source_bg(source_id))
            return {"success": True, "message": f"Analysis started for {source.name}"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/analyze-all")
    async def analyze_all_website_sources(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        try:
            sources_result = await db.execute(
                select(WebsiteSource.id).join(Message, Message.website_source_id == WebsiteSource.id)
                .filter(Message.analysis_status == "pending", WebsiteSource.is_active == True)
                .group_by(WebsiteSource.id)
            )
            source_ids = [row[0] for row in sources_result.all()]
            if not source_ids:
                return {"success": True, "message": "No website sources with pending messages found"}
            import uuid
            operation_id = f"analyze-websites-{uuid.uuid4().hex[:8]}"
            asyncio.create_task(_run_analyze_websites(source_ids, operation_id))
            return {"success": True, "message": f"Analysis started for {len(source_ids)} website source(s)", "sources": len(source_ids), "operation_id": operation_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/{source_id}/stop")
    async def stop_website_source_operation(source_id: int, db: AsyncSession = Depends(get_db)):
        from app.models import Operation
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                return {"success": False, "message": "Website source not found"}

            logger.info(f"Stop operation requested for source_id={source_id} ({source.name})")

            if source_id in website_stop_events:
                await stop_website_operation(source_id)
                result = await db.execute(select(Operation).filter(Operation.channel_username == source.name, Operation.status == "running"))
                operation = result.scalar_one_or_none()
                if operation:
                    operation.status = "stopped"
                    operation.completed_at = func.now()
                    await db.commit()
                return {"success": True, "message": "Stop signal sent"}

            result = await db.execute(select(Operation).filter(Operation.channel_username == source.name, Operation.status == "running"))
            operation = result.scalar_one_or_none()
            if operation:
                operation.status = "stopped"
                operation.completed_at = func.now()
                await db.commit()
                if source_id in website_stop_events:
                    await stop_website_operation(source_id)
                return {"success": True, "message": "Stop signal sent (cross-process)"}

            return {"success": False, "message": "No active operation found"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
