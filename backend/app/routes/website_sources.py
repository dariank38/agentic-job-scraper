"""Website source-related API routes."""

import logging
from typing import Optional
from fastapi import Depends, Form, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db
from app.models import WebsiteSource, Message
from web_crawler import Fetcher, Extractor

logger = logging.getLogger(__name__)


def detect_site_type(url: str) -> str:
    """Auto-detect site type from URL."""
    url_lower = url.lower()
    if 'v2ex.com' in url_lower:
        return 'v2ex'
    elif 'eleduck.com' in url_lower:
        return 'eleduck'
    else:
        # Default to generic (will use smart crawler)
        return 'generic'


def register_website_source_routes(app):
    """Register website source-related routes."""

    @app.get("/api/website-sources")
    async def get_website_sources(db: AsyncSession = Depends(get_db)):
        """Get all website sources."""
        result = await db.execute(select(WebsiteSource))
        sources = result.scalars().all()
        return {
            "success": True,
            "sources": [
                {
                    "id": s.id,
                    "name": s.name,
                    "url": s.url,
                    "site_type": s.site_type,
                    "is_active": s.is_active,
                    "last_fetch_new_count": s.last_fetch_new_count,
                    "last_fetch_at": s.last_fetch_at.isoformat() if s.last_fetch_at else None,
                }
                for s in sources
            ],
        }

    @app.post("/api/website-sources")
    async def add_website_source(
        name: str = Form(...),
        url: str = Form(...),
        site_type: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Add a new website source."""
        try:
            # Auto-detect site type if not provided
            if not site_type:
                site_type = detect_site_type(url)

            # Check if exists
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.url == url))
            existing = result.scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="Website source already exists")

            source = WebsiteSource(
                name=name,
                url=url,
                site_type=site_type,
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)

            return {"success": True, "source": {"id": source.id, "name": source.name, "url": source.url, "site_type": source.site_type}}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error adding source: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/website-sources/{source_id}")
    async def delete_website_source(source_id: int, db: AsyncSession = Depends(get_db)):
        """Delete a website source."""
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")

            await db.delete(source)
            await db.commit()

            return {"success": True, "message": "Website source deleted"}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error deleting source: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/api/website-sources/{source_id}")
    async def update_website_source(
        source_id: int,
        name: Optional[str] = Form(None),
        url: Optional[str] = Form(None),
        is_active: Optional[bool] = Form(None),
        extraction_prompt: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
    ):
        """Update a website source."""
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")

            if name is not None:
                source.name = name
            if url is not None:
                source.url = url
                # Re-detect site type if URL changed
                source.site_type = detect_site_type(url)
            if is_active is not None:
                source.is_active = is_active
            if extraction_prompt is not None:
                source.extraction_prompt = extraction_prompt

            source.updated_at = func.now()
            await db.commit()

            return {"success": True, "message": "Website source updated"}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error updating source: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/{source_id}/fetch")
    async def fetch_website_source(
        source_id: int,
        days_back: int = Form(0),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_db),
    ):
        """Fetch RSS content from a website source and save as Messages."""
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")

            if not source.is_active:
                raise HTTPException(status_code=400, detail="Website source is not active")

            # Use RSS fetcher to fetch RSS content
            crawler = Fetcher()
            fetch_result = await crawler.fetch(source.url)
            rss_entries = fetch_result["content"]

            if not rss_entries:
                return {
                    "success": True,
                    "new_messages": 0,
                    "fetch_method": fetch_result["type"],
                    "message": f"No RSS entries found for {source.name}",
                }

            # Save raw RSS entries as Messages (no Ollama extraction yet)
            messages_added = 0
            for entry_text in rss_entries:
                # Check if message already exists (by text hash)
                existing_result = await db.execute(
                    select(Message).filter(
                        Message.website_source_id == source_id,
                        Message.text == entry_text
                    )
                )
                existing = existing_result.scalar_one_or_none()
                if existing:
                    continue

                # Extract URL from entry for unique ID
                url = None
                for line in entry_text.split('\n'):
                    if line.startswith('Link:'):
                        url = line.replace('Link:', '').strip()
                        break

                message = Message(
                    website_post_id=f"{source_id}-{hash(entry_text)}",
                    website_source_id=source_id,
                    source_type="website",
                    text=entry_text,
                    date=None,
                    sender_username=source.name,
                    analysis_status="pending",
                )
                db.add(message)
                await db.flush()
                messages_added += 1

            # Update source
            source.last_fetch_new_count = messages_added
            source.last_fetch_at = func.now()
            await db.commit()

            return {
                "success": True,
                "new_messages": messages_added,
                "total_entries": len(rss_entries),
                "fetch_method": fetch_result["type"],
                "message": f"Fetched {messages_added} new messages from {source.name} using {fetch_result['type']}",
            }

        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error fetching from source: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/fetch-all")
    async def fetch_all_website_sources(
        days_back: int = Form(0),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_db),
    ):
        """Fetch RSS content from all active website sources and save as Messages."""
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.is_active == True))
            sources = result.scalars().all()

            if not sources:
                return {"success": True, "message": "No active website sources found"}

            total_new = 0
            fetch_methods = []

            for source in sources:
                try:
                    # Use RSS fetcher to fetch RSS content
                    crawler = Fetcher()
                    fetch_result = await crawler.fetch(source.url)
                    rss_entries = fetch_result["content"]

                    if not rss_entries:
                        continue

                    # Save raw RSS entries as Messages (no Ollama extraction yet)
                    new_count = 0
                    for entry_text in rss_entries:
                        existing_result = await db.execute(
                            select(Message).filter(
                                Message.website_source_id == source.id,
                                Message.text == entry_text
                            )
                        )
                        existing = existing_result.scalar_one_or_none()
                        if existing:
                            continue

                        message = Message(
                            website_post_id=f"{source.id}-{hash(entry_text)}",
                            website_source_id=source.id,
                            source_type="website",
                            text=entry_text,
                            date=None,
                            sender_username=source.name,
                            analysis_status="pending",
                        )
                        db.add(message)
                        await db.flush()
                        new_count += 1

                    source.last_fetch_new_count = new_count
                    source.last_fetch_at = func.now()
                    total_new += new_count
                    fetch_methods.append(fetch_result["type"])

                except Exception as e:
                    logger.error(f"[WEBSITE SOURCE] Error fetching from {source.name}: {e}", exc_info=True)
                    continue

            await db.commit()

            return {
                "success": True,
                "new_messages": total_new,
                "sources_fetched": len(sources),
                "fetch_methods": fetch_methods,
                "message": f"Fetched {total_new} new messages from {len(sources)} source(s)",
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error fetching all sources: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/{source_id}/analyze")
    async def analyze_website_source(
        source_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
    ):
        """Analyze posts from a website source in the background."""
        from app.tasks import analyze_website_posts

        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")

            if not source.is_active:
                raise HTTPException(status_code=400, detail="Website source is not active")

            # Start background analysis
            background_tasks.add_task(_analyze_website_source_bg, source_id)
            return {
                "success": True,
                "message": f"Analysis started for {source.name}",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[WEBSITE SOURCE] Error starting analysis: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/analyze-all")
    async def analyze_all_website_sources(
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
    ):
        """Analyze posts from all active website sources in the background."""
        try:
            # Find website sources with pending messages
            sources_result = await db.execute(
                select(WebsiteSource.id)
                .join(Message, Message.website_source_id == WebsiteSource.id)
                .filter(Message.analysis_status == "pending", WebsiteSource.is_active == True)
                .group_by(WebsiteSource.id)
            )
            source_ids = [row[0] for row in sources_result.all()]

            if not source_ids:
                return {"success": True, "message": "No website sources with pending messages found"}

            import uuid
            operation_id = f"analyze-websites-{uuid.uuid4().hex[:8]}"
            background_tasks.add_task(_run_analyze_websites, source_ids, operation_id)
            return {
                "success": True,
                "message": f"Analysis started for {len(source_ids)} website source(s)",
                "sources": len(source_ids),
                "operation_id": operation_id,
            }

        except Exception as e:
            logger.error(f"[WEBSITE SOURCE] Error starting bulk analysis: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


# Background task functions
async def _analyze_website_source_bg(source_id: int):
    """Background task: analyze a single website source with its own DB session."""
    from app.connection import AsyncSessionLocal
    from app.tasks import analyze_website_posts

    logger.info(f"[BG TASK] Starting analysis for website source {source_id}")
    source_name = None
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if source:
                source_name = source.name
                logger.info(f"[BG TASK] Analyzing website source {source_name} (ID: {source_id})")
                analyze_result = await analyze_website_posts(db, source)
                success = analyze_result.get("success", False)
                jobs = analyze_result.get("jobs_found", 0)
                devs = analyze_result.get("developers_found", 0)
                error = analyze_result.get("error", "unknown")
            else:
                logger.warning(f"[BG TASK] Website source {source_id} not found")
                return
        except Exception as e:
            logger.error(f"[BG TASK] Exception during analysis for website source {source_id}: {e}", exc_info=True)
            return

    if success:
        logger.info(f"[BG TASK] Completed analysis for {source_name}: {jobs} jobs, {devs} devs")
    else:
        logger.warning(f"[BG TASK] Analysis failed for {source_name}: {error}")


async def _run_analyze_websites(source_ids: list, operation_id: str):
    """Background task: analyze multiple website sources sequentially."""
    from app.connection import AsyncSessionLocal
    from app.tasks import analyze_website_posts

    success_count = 0
    error_count = 0

    logger.info(f"[BULK ANALYZE WEBSITES] Starting operation {operation_id} for {len(source_ids)} sources")

    for source_id in source_ids:
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
                source = result.scalar_one_or_none()
                if source:
                    logger.info(f"[BULK ANALYZE WEBSITES] Analyzing {source.name}")
                    await analyze_website_posts(db, source)
                    success_count += 1
                else:
                    logger.warning(f"[BULK ANALYZE WEBSITES] Source {source_id} not found")
            except Exception as e:
                error_count += 1
                logger.error(f"[BULK ANALYZE WEBSITES] Exception in source {source_id}: {e}", exc_info=True)

    logger.info(f"[BULK ANALYZE WEBSITES] Operation {operation_id} complete: {success_count} success, {error_count} errors")
