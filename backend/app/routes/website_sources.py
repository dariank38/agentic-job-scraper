"""Website source-related API routes."""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import Depends, Form, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db
from web_crawler.config import DEFAULT_DAYS_BACK
from app.models import WebsiteSource, Message, Job
from web_crawler import Fetcher, Extractor
from app.tasks import broadcast_progress, create_operation, update_operation, stop_website_operation, website_stop_events, record_fetch_outcome
from services.ollama_service import get_analyzer, is_ollama_available
from app.autonomous.budget_guard import OllamaBudgetGuard
from app.autonomous.state_manager import AutonomousStateManager

logger = logging.getLogger(__name__)


def detect_site_type(url: str) -> str:
    """Auto-detect site type from URL."""
    url_lower = url.lower()
    if 'v2ex.com' in url_lower:
        return 'v2ex'
    elif 'eleduck.com' in url_lower:
        return 'eleduck'
    elif 'bossjob.com' in url_lower:
        return 'bossjob'
    else:
        # Default to generic (will use smart crawler)
        return 'generic'


def register_website_source_routes(app):
    """Register website source-related routes."""

    @app.get("/api/website-sources")
    async def get_website_sources(db: AsyncSession = Depends(get_db)):
        """Get all website sources."""
        # Build base query with subqueries for counts
        message_count_subq = (
            select(func.count())
            .where(Message.website_source_id == WebsiteSource.id)
            .correlate(WebsiteSource)
            .scalar_subquery()
        )
        job_count_subq = (
            select(func.count())
            .where(Job.website_source_id == WebsiteSource.id, Job.is_hidden == False)
            .correlate(WebsiteSource)
            .scalar_subquery()
        )
        pending_count_subq = (
            select(func.count())
            .where(Message.website_source_id == WebsiteSource.id, Message.analysis_status == "pending")
            .correlate(WebsiteSource)
            .scalar_subquery()
        )

        query = select(
            WebsiteSource,
            message_count_subq.label("message_count"),
            job_count_subq.label("job_count"),
            pending_count_subq.label("pending_count")
        )

        # Get sources sorted by job_count DESC, message_count DESC
        sources_result = await db.execute(
            query.order_by(
                job_count_subq.desc(),
                message_count_subq.desc(),
                WebsiteSource.id
            )
        )
        sources = sources_result.all()

        return {
            "success": True,
            "sources": [
                {
                    "id": row[0].id,
                    "name": row[0].name,
                    "url": row[0].url,
                    "site_type": row[0].site_type,
                    "is_active": row[0].is_active,
                    "last_fetch_new_count": row[0].last_fetch_new_count,
                    "last_fetch_at": row[0].last_fetch_at.isoformat() if row[0].last_fetch_at else None,
                    "job_count": row[2] or 0,
                    "message_count": row[1] or 0,
                    "pending_count": row[3] or 0,
                }
                for row in sources
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
        cookies: Optional[str] = Form(None),
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
            if cookies is not None:
                source.cookies = cookies

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

    @app.post("/api/website-sources/{source_id}/toggle")
    async def toggle_website_source(
        source_id: int,
        db: AsyncSession = Depends(get_db),
    ):
        """Toggle website source active status."""
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                raise HTTPException(status_code=404, detail="Website source not found")

            source.is_active = not source.is_active
            source.updated_at = func.now()
            await db.commit()

            return {"success": True, "is_active": source.is_active}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"[WEBSITE SOURCE] Error toggling source: {e}", exc_info=True)
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

            # Create operation for tracking
            operation_id = await create_operation(db, "fetch", None, total_messages=0)
            await update_operation(db, operation_id, channel_username=source.name)

            # Broadcast start
            await broadcast_progress("fetch_start", {
                "channel": source.name,
                "channel_id": source_id,
                "operation_id": operation_id,
            })

            # Fetch based on site type — RSS for feeds, Playwright for dynamic sites
            if source.site_type == "bossjob":
                # Run bossjob fetch in background (Playwright is slow)
                asyncio.create_task(_fetch_bossjob_bg(source_id, operation_id, days_back or DEFAULT_DAYS_BACK))
                return {
                    "success": True,
                    "message": f"Bossjob fetch started for {source.name} in background (pages 1-10)",
                    "operation_id": operation_id,
                    "fetch_method": "playwright_async",
                }
            else:
                # Use RSS fetcher for RSS feeds
                crawler = Fetcher()
                fetch_result = await crawler.fetch(source.url, days_back=DEFAULT_DAYS_BACK)
                rss_entries = fetch_result["content"]

            if not rss_entries:
                await update_operation(db, operation_id, status="completed")
                await broadcast_progress("fetch_complete", {
                    "channel": source.name,
                    "new_messages": 0,
                    "operation_id": operation_id,
                })
                return {
                    "success": True,
                    "new_messages": 0,
                    "fetch_method": fetch_result["type"],
                    "message": f"No RSS entries found for {source.name}",
                }

            # Save raw RSS entries as Messages (no Ollama extraction yet)
            messages_added = 0
            total_entries = len(rss_entries)

            for idx, entry in enumerate(rss_entries):
                # Handle both old string format and new object format
                if isinstance(entry, dict):
                    entry_text = entry.get("text", "")
                    url = entry.get("link", "")
                    published_str = entry.get("published")
                    published_date = None
                    if published_str:
                        try:
                            parsed_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                            published_date = parsed_date.replace(tzinfo=None)
                        except:
                            pass
                else:
                    # Legacy string format
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
                            except:
                                pass

                # Extract post ID from URL for deduplication (e.g., 1219380 from https://www.v2ex.com/t/1219380#reply2)
                post_id = None
                if url and '/t/' in url:
                    try:
                        # Extract the number after /t/ and before # or end
                        import re
                        match = re.search(r'/t/(\d+)', url)
                        if match:
                            post_id = match.group(1)
                    except:
                        pass

                # Check for duplicate: by post_id first, then fall back to text content
                if post_id:
                    existing_result = await db.execute(
                        select(Message).filter(
                            Message.website_post_id == f"{source_id}-{post_id}"
                        )
                    )
                else:
                    existing_result = await db.execute(
                        select(Message).filter(
                            Message.text == entry_text
                        )
                    )
                existing = existing_result.scalars().first()
                if existing:
                    continue

                message = Message(
                    website_post_id=f"{source_id}-{post_id}" if post_id else f"{source_id}-{hash(entry_text)}",
                    website_source_id=source_id,
                    source_type="website",
                    text=entry_text,
                    analysis_text=entry.get("analysis_text") if isinstance(entry, dict) else None,  # Condensed text for Ollama analysis
                    date=published_date,
                    sender_username=source.name,
                    analysis_status="pending",
                )
                db.add(message)
                await db.flush()
                messages_added += 1

                # Broadcast progress
                if messages_added % 5 == 0:
                    await broadcast_progress("fetch_progress", {
                        "channel": source.name,
                        "processed": idx + 1,
                        "total": total_entries,
                        "operation_id": operation_id,
                    })

            # Update source last fetch info
            source.last_fetch_new_count = messages_added
            source.last_fetch_at = datetime.utcnow()

            await db.commit()
            await update_operation(db, operation_id, status="completed")
            await broadcast_progress("fetch_complete", {
                "channel": source.name,
                "new_messages": messages_added,
                "operation_id": operation_id,
            })
            return {
                "success": True,
                "new_messages": messages_added,
                "fetch_method": fetch_result["type"],
                "message": f"Added {messages_added} messages from {source.name}",
            }

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
        """Fetch RSS content from all active website sources and save as Messages."""
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.is_active == True))
            sources = result.scalars().all()

            if not sources:
                return {"success": True, "message": "No active website sources found"}

            total_new = 0
            fetch_methods = []

            for source in sources:
                fetch_start = datetime.now()
                fetch_error = None
                new_jobs_count = 0
                
                try:
                    # Fetch based on site type
                    if source.site_type == "bossjob":
                        # Use Playwright for bossjob.com
                        from web_crawler import fetch_posts
                        
                        # Initialize analyzer and budget_guard if Ollama is available
                        analyzer = None
                        budget_guard = None
                        state_manager = None
                        if await is_ollama_available():
                            analyzer = get_analyzer()
                            budget_guard = OllamaBudgetGuard(db)
                            state_manager = AutonomousStateManager(db)
                            await budget_guard.initialize()
                        
                        posts = await fetch_posts(
                            source.url,
                            site_type="bossjob",
                            days_back=days_back or DEFAULT_DAYS_BACK,
                            analyzer=analyzer,
                            budget_guard=budget_guard,
                            state_manager=state_manager,
                        )
                        rss_entries = [
                            {
                                "text": post.get("text", ""),
                                "link": post.get("url", ""),
                                "published": post.get("date").isoformat() if post.get("date") else None,
                            }
                            for post in posts
                        ]
                    else:
                        # Use RSS fetcher for RSS feeds
                        crawler = Fetcher()
                        fetch_result = await crawler.fetch(source.url, days_back=days_back or DEFAULT_DAYS_BACK)
                        rss_entries = fetch_result["content"]

                    if not rss_entries:
                        continue

                    # Save raw RSS entries as Messages (no Ollama extraction yet)
                    new_count = 0
                    for entry in rss_entries:
                        # Handle both old string format and new object format
                        if isinstance(entry, dict):
                            entry_text = entry.get("text", "")
                            url = entry.get("link", "")
                            published_str = entry.get("published")
                            published_date = None
                            if published_str:
                                try:
                                    parsed_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                                    published_date = parsed_date.replace(tzinfo=None)
                                except:
                                    pass
                        else:
                            # Legacy string format
                            entry_text = entry
                            url = None
                            published_date = None
                            for line in entry_text.split('\n'):
                                if line.startswith('Link:'):
                                    url = line.replace('Link:', '').strip()
                                    break

                        # Extract post ID from URL for deduplication
                        post_id = None
                        if url and '/t/' in url:
                            try:
                                import re
                                match = re.search(r'/t/(\d+)', url)
                                if match:
                                    post_id = match.group(1)
                            except:
                                pass

                        # Check for duplicate: by post_id first, then fall back to text content
                        if post_id:
                            existing_result = await db.execute(
                                select(Message).filter(
                                    Message.website_post_id == f"{source.id}-{post_id}"
                                )
                            )
                        else:
                            existing_result = await db.execute(
                                select(Message).filter(
                                    Message.text == entry_text
                                )
                            )
                        existing = existing_result.scalars().first()
                        if existing:
                            continue

                        message = Message(
                            website_post_id=f"{source.id}-{post_id}" if post_id else f"{source.id}-{hash(entry_text)}",
                            website_source_id=source.id,
                            source_type="website",
                            text=entry_text,
                            date=published_date,
                            sender_username=source.name,
                            analysis_status="pending",
                        )
                        db.add(message)
                        await db.flush()
                        new_count += 1

                    source.last_fetch_new_count = new_count
                    source.last_fetch_at = func.now()
                    total_new += new_count
                    fetch_methods.append(fetch_result["type"] if source.site_type != "bossjob" else "playwright")
                    
                    # Record fetch outcome for schedule optimization
                    duration = int((datetime.now() - fetch_start).total_seconds())
                    await record_fetch_outcome(
                        source_id=source.id,
                        source_type="website",
                        new_jobs=new_jobs_count,
                        new_messages=new_count,
                        duration_seconds=duration,
                    )

                except Exception as e:
                    fetch_error = e
                    logger.error(f"[WEBSITE SOURCE] Error fetching from {source.name}: {e}", exc_info=True)
                    
                    # Record fetch outcome with error
                    duration = int((datetime.now() - fetch_start).total_seconds())
                    await record_fetch_outcome(
                        source_id=source.id,
                        source_type="website",
                        new_jobs=0,
                        new_messages=0,
                        duration_seconds=duration,
                        error=e,
                    )
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
            asyncio.create_task(_analyze_website_source_bg(source_id))
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
            asyncio.create_task(_run_analyze_websites(source_ids, operation_id))
            return {
                "success": True,
                "message": f"Analysis started for {len(source_ids)} website source(s)",
                "sources": len(source_ids),
                "operation_id": operation_id,
            }

        except Exception as e:
            logger.error(f"[WEBSITE SOURCE] Error starting bulk analysis: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/website-sources/{source_id}/stop")
    async def stop_website_source_operation(
        source_id: int,
        db: AsyncSession = Depends(get_db)
    ):
        """Stop the current fetch or analyze operation for a website source."""
        from app.models import Operation
        from sqlalchemy import select as sa_select
        try:
            # Get source name first
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                return {"success": False, "message": "Website source not found"}

            logger.info(f"Stop operation requested for source_id={source_id} ({source.name})")
            logger.info(f"Current website stop events in memory: {list(website_stop_events.keys())}")

            # Check in-memory (fast path)
            if source_id in website_stop_events:
                await stop_website_operation(source_id)
                logger.info(f"Stop signal sent via memory for source_id={source_id}")

                # Also update any running operation in database by channel_username
                result = await db.execute(
                    sa_select(Operation).filter(
                        Operation.channel_username == source.name,
                        Operation.status == "running"
                    )
                )
                operation = result.scalar_one_or_none()
                if operation:
                    operation.status = "stopped"
                    operation.completed_at = func.now()
                    await db.commit()
                    logger.info(f"Operation marked as stopped in database for {source.name}")

                return {"success": True, "message": "Stop signal sent"}

            # Check database for running operation (cross-process) by channel_username
            result = await db.execute(
                sa_select(Operation).filter(
                    Operation.channel_username == source.name,
                    Operation.status == "running"
                )
            )
            operation = result.scalar_one_or_none()
            if operation:
                # Mark operation as stopped in database
                operation.status = "stopped"
                operation.completed_at = func.now()
                await db.commit()
                logger.info(f"Operation marked as stopped in database for {source.name}")

                # Try to stop via memory if available
                if source_id in website_stop_events:
                    await stop_website_operation(source_id)
                    logger.info(f"Also sent memory signal for source_id={source_id}")

                return {"success": True, "message": "Stop signal sent (cross-process)"}

            logger.warning(f"No active operation found for source_id={source_id} ({source.name})")
            return {"success": False, "message": "No active operation found"}

        except Exception as e:
            logger.error(f"[WEBSITE SOURCE] Error stopping operation: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


def is_software_engineering_job(title: str, requirements: str = "", description: str = "") -> bool:
    """Check if job title, requirements or description are software engineering related.

    Uses two tiers:
    - Strong keywords: unambiguous SE phrases checked against title + requirements + description.
    - Title-only keywords: broad tech words that could appear in any job description,
      so they are only checked against the job title to avoid false positives.
    """
    if not title and not requirements and not description:
        return False

    title_lower = title.lower()
    full_text_lower = f"{title} {requirements} {description}".lower()

    # Strong SE keywords — safe to match anywhere in the full text
    strong_keywords = [
        'software engineer', 'software developer', 'full stack', 'fullstack',
        'backend developer', 'frontend developer', 'back-end developer', 'front-end developer',
        'web developer', 'web engineer',
        'mobile developer', 'ios developer', 'android developer',
        'devops engineer', 'sre', 'site reliability engineer', 'platform engineer', 'cloud engineer',
        'data engineer', 'data scientist', 'machine learning engineer', 'ml engineer', 'ai engineer',
        'java developer', 'python developer', 'javascript developer', 'typescript developer',
        'qa engineer', 'quality assurance engineer', 'test engineer', 'automation engineer',
        'embedded engineer', 'firmware engineer', 'systems engineer',
        'blockchain developer', 'web3 developer', 'smart contract', 'solidity developer',
        'engineering manager', 'tech lead', 'principal engineer',
        'staff engineer', 'security engineer', 'cybersecurity engineer', 'penetration tester',
        'game developer', 'unity developer', 'unreal developer',
        'api developer', 'api engineer', 'microservices',
        'database administrator', 'dba',
    ]

    # Title-only keywords — too generic to match in descriptions (risk false positives)
    title_only_keywords = [
        'backend', 'frontend', 'front end', 'back end',
        'devops', 'developer', 'engineer',
        'python', 'javascript', 'typescript', 'golang', 'kotlin', 'flutter',
        'react', 'vue', 'angular', 'node.js', 'nodejs', 'next.js', 'django', 'fastapi',
        'rust', 'dart', 'swift',
        'aws', 'gcp', 'azure', 'cloud', 'kubernetes', 'docker',
        'sql', 'postgresql', 'mysql', 'mongodb', 'database',
        'blockchain', 'web3',
    ]

    # Strong SE keywords (Chinese) — safe to match anywhere
    strong_keywords_zh = [
        '软件工程师', '软件开发', '全栈', '后端开发', '前端开发', '网页开发',
        '移动开发', 'ios开发', 'android开发', '安卓开发',
        '运维工程师', '测试工程师', '质量保证工程师', '自动化测试工程师',
        '数据工程师', '数据科学家', '机器学习工程师', '人工智能工程师', 'ai工程师',
        'python开发', 'java开发',
        '嵌入式工程师', '固件工程师', '系统工程师', '云工程师', '平台工程师',
        '区块链开发', '智能合约开发',
        '技术经理', '技术主管', '首席工程师',
        '资深工程师', '高级工程师', '初级工程师',
        '安全工程师', '游戏开发工程师',
    ]

    # Title-only keywords (Chinese)
    title_only_keywords_zh = [
        '后端', '前端', '开发工程师', '开发者',
        'javascript', 'typescript', 'react', 'vue', 'angular',
        '数据库管理', '云计算',
    ]

    # Check strong keywords against full text
    for keyword in strong_keywords:
        if keyword in full_text_lower:
            return True

    # Check title-only keywords against title only
    for keyword in title_only_keywords:
        if keyword in title_lower:
            return True

    # Check Chinese strong keywords against full text
    full_text_original = f"{title} {requirements} {description}"
    for keyword in strong_keywords_zh:
        if keyword in full_text_original:
            return True

    # Check Chinese title-only keywords against title only
    for keyword in title_only_keywords_zh:
        if keyword in title:
            return True

    return False


async def _fetch_bossjob_bg(source_id: int, operation_id: str, days_back: int):
    """Background task: fetch bossjob.com jobs with Playwright."""
    from app.connection import AsyncSessionLocal
    from app.models import Message, WebsiteSource
    from web_crawler import fetch_posts
    from app.tasks import update_operation, broadcast_progress, record_fetch_outcome

    async with AsyncSessionLocal() as db:
        fetch_start = datetime.now()
        fetch_error = None
        
        try:
            result = await db.execute(select(WebsiteSource).filter(WebsiteSource.id == source_id))
            source = result.scalar_one_or_none()
            if not source:
                logger.warning(f"[BG FETCH BOSSJOB] Source {source_id} not found")
                return

            logger.info(f"[BG FETCH BOSSJOB] Starting fetch for {source.name}")
            await broadcast_progress("fetch_start", {
                "channel": source.name,
                "channel_id": source_id,
                "operation_id": operation_id,
            })

            # Fetch with Playwright
            import json
            cookies = None
            if source.cookies:
                try:
                    cookies = json.loads(source.cookies)
                    if not isinstance(cookies, list):
                        cookies = [cookies]
                except json.JSONDecodeError:
                    logger.warning(f"[BG FETCH BOSSJOB] Invalid cookies JSON for source {source_id}")

            # Initialize analyzer and budget_guard if Ollama is available
            analyzer = None
            budget_guard = None
            state_manager = None
            if await is_ollama_available():
                analyzer = get_analyzer()
                budget_guard = OllamaBudgetGuard(db)
                state_manager = AutonomousStateManager(db)
                await budget_guard.initialize()
            
            posts = await fetch_posts(
                source.url,
                site_type="bossjob",
                days_back=days_back,
                cookies=cookies,
                analyzer=analyzer,
                budget_guard=budget_guard,
                state_manager=state_manager,
            )

            if not posts:
                logger.info(f"[BG FETCH BOSSJOB] No posts found for {source.name}")
                await update_operation(db, operation_id, status="completed")
                await broadcast_progress("fetch_complete", {
                    "channel": source.name,
                    "new_messages": 0,
                    "operation_id": operation_id,
                })
                return

            # Save posts as Jobs directly (Bossjob has structured data)
            jobs_added = 0
            jobs_filtered = 0
            for post in posts:
                try:
                    title = post.get("title", "")
                    requirements = post.get("requirements", "")
                    description = post.get("description", "")
                    
                    # Filter: only save software engineering jobs (check title, requirements, description)
                    if not is_software_engineering_job(title, requirements, description):
                        jobs_filtered += 1
                        logger.info(f"[BG FETCH BOSSJOB] Filtered non-SE job: {title[:50]}...")
                        continue
                    
                    post_id = post.get("id", f"{source_id}-{hash(post.get('text', ''))}")
                    job_url = post.get("url", "")
                    
                    # Check for duplicate by URL
                    existing_job = await db.execute(
                        select(Job).filter(
                            Job.website_source_id == source_id,
                            Job.summary.like(f"%{job_url}%")  # URL stored in summary for dedup
                        )
                    )
                    if existing_job.scalar_one_or_none():
                        continue

                    # Create Job record directly from structured Bossjob data
                    job = Job(
                        website_source_id=source_id,
                        channel_name=source.name,
                        source_type="website",
                        title=title,
                        company=post.get("company", ""),
                        location=post.get("location", ""),
                        summary=post.get("description", "") + f"\n\nURL: {job_url}",
                        skills=post.get("requirements", ""),  # Store requirements in skills field
                        contact=job_url,  # Store job URL as contact link
                        contact_type="url",
                        is_applied=False,
                        is_hidden=False,
                    )
                    db.add(job)
                    jobs_added += 1
                except Exception as e:
                    logger.warning(f"[BG FETCH BOSSJOB] Error saving job: {e}")
                    continue

            await db.commit()
            source.last_fetch_at = datetime.now()
            source.last_fetch_new_count = jobs_added
            await db.commit()

            # Record fetch outcome for schedule optimization
            duration = int((datetime.now() - fetch_start).total_seconds())
            await record_fetch_outcome(
                source_id=source_id,
                source_type="website",
                new_jobs=jobs_added,
                new_messages=0,
                duration_seconds=duration,
            )

            await update_operation(db, operation_id, status="completed")
            await broadcast_progress("fetch_complete", {
                "channel": source.name,
                "new_messages": jobs_added,
                "operation_id": operation_id,
            })

            logger.info(f"[BG FETCH BOSSJOB] Completed: {jobs_added} new jobs, {jobs_filtered} filtered (non-SE) from {source.name}")

        except Exception as e:
            fetch_error = e
            logger.error(f"[BG FETCH BOSSJOB] Error: {e}", exc_info=True)
            
            # Record fetch outcome with error
            duration = int((datetime.now() - fetch_start).total_seconds())
            await record_fetch_outcome(
                source_id=source_id,
                source_type="website",
                new_jobs=0,
                new_messages=0,
                duration_seconds=duration,
                error=e,
            )
            
            try:
                await update_operation(db, operation_id, status="error", error_message=str(e))
            except Exception:
                pass


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
