"""Action-related API routes (fetch, analyze, search)."""

import logging
from datetime import datetime
from typing import Optional
from fastapi import BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db, AsyncSessionLocal

logger = logging.getLogger(__name__)
from app.models import AnalysisRun, Channel, Message, Operation
from app.tasks import analyze_messages, fetch_and_store_messages, reset_bulk_stop_event, is_bulk_operation_stopped, cleanup_bulk_stop_event, stop_bulk_operation, _to_str, _to_bool, start_telegram_listener, stop_telegram_listener, is_listener_running, add_listener_channels, remove_listener_channels, get_listener_channels


def register_action_routes(app):
    """Register action-related routes."""

    async def _fetch_channel_bg(channel_id: int, account_id: Optional[int] = None):
        """Background task: fetch messages from a single channel with its own DB session."""
        logger.info(f"[BG TASK] Starting fetch for channel {channel_id}")
        channel_name = None
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                channel = result.scalar_one_or_none()
                if channel:
                    channel_name = channel.username or channel.name or f"ID:{channel_id}"
                    logger.info(f"[BG TASK] Fetching from @{channel_name} (ID: {channel_id})")
                    
                    from telegram_processor.config import DEFAULT_DAYS_BACK
                    days_back = DEFAULT_DAYS_BACK
                    
                    fetch_result = await fetch_and_store_messages(
                        db,
                        channel,
                        days_back=days_back,
                        account_id=account_id
                    )
                    new_messages = fetch_result.get("new_stored", 0)
                    logger.info(f"[BG TASK] Completed fetch for @{channel_name}: {new_messages} new messages")
                else:
                    logger.warning(f"[BG TASK] Channel {channel_id} not found")
            except Exception as e:
                logger.error(f"[BG TASK] Exception during fetch for channel {channel_id}: {e}", exc_info=True)

    @app.post("/api/fetch/{channel_id}")
    async def fetch_channel(channel_id: int, account_id: Optional[int] = None, background_tasks: BackgroundTasks = None, db: AsyncSession = Depends(get_db)):
        """Fetch messages from a Telegram channel (runs in background)."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            # Start background task
            background_tasks.add_task(_fetch_channel_bg, channel_id, account_id)

            return {
                "success": True,
                "message": f"Fetch started for @{channel.username}",
                "channel": channel.username
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start fetch: {str(e)}")

    async def _analyze_channel_bg(channel_id: int):
        """Background task: analyze a single channel with its own DB session."""
        logger.info(f"[BG TASK] Starting analysis for channel {channel_id}")
        channel_name = None
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                channel = result.scalar_one_or_none()
                if channel:
                    channel_name = channel.username or channel.name or f"ID:{channel_id}"
                    logger.info(f"[BG TASK] Analyzing channel @{channel_name} (ID: {channel_id})")
                    analyze_result = await analyze_messages(db, channel)
                    # Check result outside the try block to avoid session issues
                    success = analyze_result.get("success", False)
                    jobs = analyze_result.get("jobs_found", 0)
                    devs = analyze_result.get("developers_found", 0)
                    error = analyze_result.get("error", "unknown")
                else:
                    logger.warning(f"[BG TASK] Channel {channel_id} not found")
                    return
            except Exception as e:
                logger.error(f"[BG TASK] Exception during analysis for channel {channel_id}: {e}", exc_info=True)
                return
        
        # Log results outside async with block (session already closed)
        if success:
            logger.info(f"[BG TASK] Completed analysis for @{channel_name}: {jobs} jobs, {devs} devs")
        else:
            logger.warning(f"[BG TASK] Analysis failed for @{channel_name}: {error}")

    @app.post("/api/analyze/{channel_id}")
    async def analyze_channel(channel_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        """Analyze messages in a channel (runs in background)."""
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            # Check if there are pending messages to analyze
            pending_result = await db.execute(
                select(func.count(Message.id)).filter(
                    Message.channel_id == channel_id,
                    Message.analysis_status == "pending",
                )
            )
            pending_count = pending_result.scalar() or 0

            if pending_count == 0:
                return {"success": True, "message": "No pending messages to analyze", "analyzed": 0}

            # Check if analyze already running for this channel
            existing_op = await db.execute(
                select(Operation).filter(
                    Operation.channel_id == channel_id,
                    Operation.operation_type == "analyze",
                    Operation.status == "running"
                )
            )
            if existing_op.scalar_one_or_none():
                return {"success": False, "message": "Analysis already running for this channel"}

            # Start analysis in background
            background_tasks.add_task(_analyze_channel_bg, channel_id)

            return {
                "success": True,
                "message": f"Analysis started for {pending_count} pending message(s)",
                "analyzed": 0,  # Will be updated via WebSocket
                "pending": pending_count
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")

    async def _run_fetch_all(channel_ids: list, operation_id: str):
        """Background task: fetch messages from each channel sequentially, each with its own DB session."""
        from app.tasks import broadcast_progress
        
        logger.info(f"[BULK FETCH] Starting operation {operation_id} for {len(channel_ids)} channels")
        await reset_bulk_stop_event(operation_id)
        success_count = 0
        error_count = 0
        total_new_messages = 0
        
        from telegram_processor.config import DEFAULT_DAYS_BACK
        days_back = DEFAULT_DAYS_BACK
        
        # Broadcast bulk operation start
        await broadcast_progress("bulk_fetch_start", {
            "operation_id": operation_id,
            "total_channels": len(channel_ids)
        })
        
        try:
            for idx, channel_id in enumerate(channel_ids):
                if is_bulk_operation_stopped(operation_id):
                    logger.info(f"[BULK FETCH] Operation {operation_id} stopped by user at channel {idx+1}/{len(channel_ids)}")
                    await broadcast_progress("bulk_fetch_stopped", {
                        "operation_id": operation_id,
                        "progress": idx,
                        "total": len(channel_ids)
                    })
                    break
                async with AsyncSessionLocal() as db:
                    try:
                        result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                        channel = result.scalar_one_or_none()
                        if channel:
                            logger.info(f"[BULK FETCH] {operation_id} | Channel {idx+1}/{len(channel_ids)}: @{channel.username}")
                            fetch_result = await fetch_and_store_messages(
                                db,
                                channel,
                                days_back=days_back
                            )
                            new_messages = fetch_result.get("new_stored", 0)
                            total_new_messages += new_messages
                            success_count += 1
                            logger.info(f"[BULK FETCH] ✓ Channel {channel_id} complete: {new_messages} new messages")
                            
                            # Broadcast progress for bulk operation
                            await broadcast_progress("bulk_fetch_progress", {
                                "operation_id": operation_id,
                                "progress": idx + 1,
                                "total": len(channel_ids),
                                "channel": channel.username,
                                "new_messages": new_messages
                            })
                        else:
                            logger.warning(f"[BULK FETCH] Channel {channel_id} not found")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"[BULK FETCH] Exception in channel {channel_id}: {e}", exc_info=True)
            
            # Broadcast completion
            await broadcast_progress("bulk_fetch_complete", {
                "operation_id": operation_id,
                "success_count": success_count,
                "error_count": error_count,
                "total_new_messages": total_new_messages
            })
            logger.info(f"[BULK FETCH] Operation {operation_id} complete: {success_count} success, {error_count} errors, {total_new_messages} new messages")
        finally:
            cleanup_bulk_stop_event(operation_id)

    @app.post("/api/fetch-all")
    async def fetch_all(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        """Fetch messages from all active channels in the background and return immediately."""
        try:
            # Cleanup stale operations before starting bulk fetch
            from app.tasks import cleanup_stale_operations
            await cleanup_stale_operations()

            result = await db.execute(select(Channel).filter(Channel.is_active == True))
            channels = result.scalars().all()
            
            if not channels:
                return {"success": False, "message": "No active channels found"}

            # Generate bulk operation ID for stop support
            import uuid
            operation_id = f"fetch-all-{uuid.uuid4().hex[:8]}"
            await reset_bulk_stop_event(operation_id)

            # Start background task
            channel_ids = [c.id for c in channels]
            background_tasks.add_task(_run_fetch_all, channel_ids, operation_id)

            return {
                "success": True,
                "message": f"Fetch started for {len(channels)} channel(s)",
                "operation_id": operation_id,
                "channels": len(channels)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start fetch all: {str(e)}")

    async def _run_analyze_all(channel_ids: list, operation_id: str):
        """Background task: analyze each channel sequentially, each with its own DB session."""
        logger.info(f"[BULK ANALYZE] Starting operation {operation_id} for {len(channel_ids)} channels")
        await reset_bulk_stop_event(operation_id)
        success_count = 0
        error_count = 0
        try:
            for idx, channel_id in enumerate(channel_ids):
                if is_bulk_operation_stopped(operation_id):
                    logger.info(f"[BULK ANALYZE] Operation {operation_id} stopped by user at channel {idx+1}/{len(channel_ids)}")
                    break
                async with AsyncSessionLocal() as db:
                    try:
                        result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                        channel = result.scalar_one_or_none()
                        if channel:
                            logger.info(f"[BULK ANALYZE] {operation_id} | Channel {idx+1}/{len(channel_ids)}: @{channel.username}")
                            analyze_result = await analyze_messages(db, channel, bulk_operation_id=operation_id)
                            if analyze_result.get("success"):
                                success_count += 1
                                logger.info(f"[BULK ANALYZE] ✓ Channel {channel_id} complete: {analyze_result.get('jobs_found', 0)} jobs")
                            else:
                                error_count += 1
                                logger.warning(f"[BULK ANALYZE] ✗ Channel {channel_id} failed: {analyze_result.get('error', 'unknown')}")
                        else:
                            logger.warning(f"[BULK ANALYZE] Channel {channel_id} not found")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"[BULK ANALYZE] Exception in channel {channel_id}: {e}", exc_info=True)
            logger.info(f"[BULK ANALYZE] Operation {operation_id} complete: {success_count} success, {error_count} errors")
        finally:
            cleanup_bulk_stop_event(operation_id)

    @app.post("/api/analyze-all")
    async def analyze_all(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        """Start analysis for channels with pending messages in the background and return immediately."""
        # Cleanup stale operations before starting bulk analyze
        from app.tasks import cleanup_stale_operations
        await cleanup_stale_operations()

        # Find channels that have pending messages to analyze
        channels_result = await db.execute(
            select(Channel.id)
            .join(Message, Message.channel_id == Channel.id)
            .filter(Message.analysis_status == "pending")
            .group_by(Channel.id)
        )
        channel_ids = [row[0] for row in channels_result.all()]

        if not channel_ids:
            return {"success": True, "message": "No channels with pending messages found"}
        import uuid
        operation_id = f"analyze-all-{uuid.uuid4().hex[:8]}"
        background_tasks.add_task(_run_analyze_all, channel_ids, operation_id)
        return {"success": True, "message": f"Analysis started for {len(channel_ids)} channel(s)", "channels": len(channel_ids), "operation_id": operation_id}

    @app.post("/api/reanalyze")
    async def reanalyze_messages(db: AsyncSession = Depends(get_db)):
        """Re-analyze messages marked for re-analysis."""
        try:
            from app.models import Message

            result = await db.execute(
                select(Message).filter(Message.needs_reanalysis == True)
            )
            messages = result.scalars().all()

            reanalyzed = 0
            for message in messages:
                try:
                    # BUG FIX: Fetch channel from database since channel variable was undefined
                    channel_result = await db.execute(select(Channel).filter(Channel.id == message.channel_id))
                    channel = channel_result.scalar_one_or_none()

                    from services.ollama_service import get_analyzer
                    analyzer = get_analyzer()
                    analysis = await analyzer.analyze_message(message.text)

                    if analysis.get("category") == "job_posting":
                        from app.models import Job
                        job_data = analysis.get("job_posting", {})
                        job_result = await db.execute(select(Job).filter(Job.message_id == message.id))
                        job = job_result.scalar_one_or_none()

                        _summary = job_data.get("summary") or ""
                        _title = job_data.get("title") or (_summary.split(".")[0].strip()[:200] if _summary else None)
                        if job:
                            job.title = _title
                            job.company = job_data.get("company")
                            job.location = job_data.get("location")
                            job.is_remote = _to_bool(job_data.get("is_remote"))
                            job.role_type = _to_str(job_data.get("role_type"))
                            job.skills = job_data.get("skills")
                            job.contact = job_data.get("contact")
                            job.summary = job_data.get("summary")
                            job.translated_text = analysis.get("translated_text")
                            job.confidence = analysis.get("confidence")
                            job.analyzed_at = datetime.utcnow()
                            job.needs_reanalysis = False
                        else:
                            new_job = Job(
                                message_id=message.id,
                                channel_id=message.channel_id,
                                channel_name=channel.name if channel else None,  # channel is now defined
                                source_type="telegram",
                                title=_title,
                                company=job_data.get("company"),
                                location=job_data.get("location"),
                                is_remote=_to_bool(job_data.get("is_remote")),
                                role_type=_to_str(job_data.get("role_type")),
                                skills=job_data.get("skills"),
                                contact=job_data.get("contact"),
                                summary=job_data.get("summary"),
                                translated_text=analysis.get("translated_text"),
                                confidence=analysis.get("confidence"),
                            )
                            db.add(new_job)
                            message.needs_reanalysis = False

                    elif analysis.get("category") == "personal_info":
                        from app.models import Developer
                        dev_data = analysis.get("personal_info", {})
                        dev_result = await db.execute(select(Developer).filter(Developer.message_id == message.id))
                        dev = dev_result.scalar_one_or_none()

                        if dev:
                            dev.name = dev_data.get("name")
                            dev.skills = dev_data.get("skills")
                            dev.experience = dev_data.get("experience")
                            dev.contact = dev_data.get("contact")
                            dev.looking_for_work = dev_data.get("looking_for_work")
                            dev.summary = dev_data.get("summary")
                            dev.translated_text = analysis.get("translated_text")
                            dev.confidence = analysis.get("confidence")
                            dev.analyzed_at = datetime.utcnow()
                            message.needs_reanalysis = False
                        else:
                            new_dev = Developer(
                                message_id=message.id,
                                channel_id=message.channel_id,
                                name=dev_data.get("name"),
                                skills=dev_data.get("skills"),
                                experience=dev_data.get("experience"),
                                contact=dev_data.get("contact"),
                                looking_for_work=dev_data.get("looking_for_work"),
                                summary=dev_data.get("summary"),
                                translated_text=analysis.get("translated_text"),
                                confidence=analysis.get("confidence"),
                            )
                            db.add(new_dev)
                            message.needs_reanalysis = False

                    else:
                        message.needs_reanalysis = False

                    reanalyzed += 1
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    continue

            return {"success": True, "reanalyzed": reanalyzed}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reanalyze: {str(e)}")

    @app.post("/api/reanalyze-skipped")
    async def reanalyze_skipped_messages(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        """Re-analyze all messages that were skipped."""
        try:
            from app.models import Message
            from sqlalchemy import func
            import uuid

            # Count skipped messages per channel (more memory efficient than loading all)
            result = await db.execute(
                select(Message.channel_id, func.count(Message.id).label("count"))
                .filter(Message.analysis_status == "skipped")
                .group_by(Message.channel_id)
            )
            channel_counts = result.all()

            if not channel_counts:
                return {"success": True, "message": "No skipped messages to re-analyze"}

            channel_ids = [row[0] for row in channel_counts]
            total_skipped = sum(row[1] for row in channel_counts)

            # Generate bulk operation ID for stop support
            operation_id = f"reanalyze-skipped-{uuid.uuid4().hex[:8]}"

            # Run in background
            background_tasks.add_task(_run_reanalyze_skipped, channel_ids, operation_id)

            return {
                "success": True,
                "message": f"Re-analysis started for {total_skipped} skipped message(s) across {len(channel_ids)} channel(s)",
                "operation_id": operation_id,
                "total_skipped": total_skipped,
                "channels": len(channel_ids),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to re-analyze skipped messages: {str(e)}")

    async def _run_reanalyze_skipped(channel_ids: list, operation_id: str):
        """Background task: re-analyze skipped messages for each channel."""
        logger.info(f"[REANALYZE SKIPPED] Starting operation {operation_id} for {len(channel_ids)} channels")
        await reset_bulk_stop_event(operation_id)
        success_count = 0
        error_count = 0
        try:
            for idx, channel_id in enumerate(channel_ids):
                if is_bulk_operation_stopped(operation_id):
                    logger.info(f"[REANALYZE SKIPPED] Operation {operation_id} stopped by user at channel {idx+1}/{len(channel_ids)}")
                    break

                async with AsyncSessionLocal() as channel_db:
                    try:
                        channel_result = await channel_db.execute(
                            select(Channel).filter(Channel.id == channel_id)
                        )
                        channel = channel_result.scalar_one_or_none()

                        if not channel:
                            logger.warning(f"[REANALYZE SKIPPED] Channel {channel_id} not found")
                            continue

                        # Reset skipped messages to pending
                        await channel_db.execute(
                            Message.__table__.update()
                            .where(
                                (Message.channel_id == channel_id) &
                                (Message.analysis_status == "skipped")
                            )
                            .values(analysis_status="pending")
                        )
                        await channel_db.commit()

                        # Analyze the channel with bulk operation ID
                        result = await analyze_messages(channel_db, channel, bulk_operation_id=operation_id)
                        if result.get("success"):
                            success_count += 1
                            logger.info(f"[REANALYZE SKIPPED] ✓ Channel @{channel.username} complete")
                        else:
                            error_count += 1
                            logger.warning(f"[REANALYZE SKIPPED] ✗ Channel @{channel.username} failed: {result.get('error')}")

                    except Exception as channel_error:
                        error_count += 1
                        logger.error(f"[REANALYZE SKIPPED] Exception in channel {channel_id}: {channel_error}", exc_info=True)

            logger.info(f"[REANALYZE SKIPPED] Operation {operation_id} complete: {success_count} success, {error_count} errors")
        finally:
            cleanup_bulk_stop_event(operation_id)

    @app.post("/api/reanalyze-message/{message_id}")
    async def reanalyze_single_message(message_id: int, db: AsyncSession = Depends(get_db)):
        """Re-analyze a single skipped message."""
        try:
            from app.models import Message, Job, Developer
            from app.tasks import _analyze_single
            from services.ollama_service import get_analyzer, is_ollama_available

            if not await is_ollama_available():
                raise HTTPException(status_code=500, detail="Ollama not available")

            result = await db.execute(select(Message).filter(Message.id == message_id))
            message = result.scalar_one_or_none()
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            # Fetch channel for channel_name reference
            from app.models import Channel
            channel_result = await db.execute(select(Channel).filter(Channel.id == message.channel_id))
            channel = channel_result.scalar_one_or_none()

            # Reset status to pending
            message.analysis_status = "pending"
            await db.commit()

            # Analyze the message
            analyzer = get_analyzer()
            channel_username = channel.username if channel else "unknown"
            message, result, error = await _analyze_single(analyzer, message, channel_username)

            if error:
                message.analysis_status = "skipped"
                await db.commit()
                raise HTTPException(status_code=500, detail=f"Analysis failed: {str(error)}")

            if not result or result.get("category") == "other":
                message.analysis_status = "skipped"
                await db.commit()
                return {"success": True, "analyzed": False, "reason": "No relevant content found"}

            # Process the result
            category = result.get("category", "other")
            confidence = result.get("confidence")
            translated_text = result.get("translated_text")

            if category == "job_posting" and result.get("job_posting"):
                job_data = result.get("job_posting", {})
                is_remote = _to_bool(job_data.get("is_remote"))
                if is_remote is False:
                    message.analysis_status = "skipped"
                    await db.commit()
                    return {"success": True, "analyzed": False, "reason": "On-site job filtered"}

                location = job_data.get("location")
                if isinstance(location, list):
                    location = ", ".join(location)

                contact = job_data.get("contact")
                if isinstance(contact, list):
                    contact = ", ".join(contact)

                contact_type = job_data.get("contact_type")
                if isinstance(contact_type, list):
                    contact_type = ", ".join(contact_type)

                role_type = job_data.get("role_type")
                if isinstance(role_type, list):
                    role_type = ", ".join(role_type)

                summary_str = job_data.get("summary") or ""
                title = job_data.get("title") or (summary_str.split(".")[0].strip()[:200] if summary_str else None)
                company = job_data.get("company")
                if title and company:
                    existing_job_result = await db.execute(
                        select(Job).filter(
                            Job.title == title,
                            Job.company == company,
                        )
                    )
                    existing_job = existing_job_result.scalar_one_or_none()
                    if existing_job:
                        message.analysis_status = "skipped"
                        await db.commit()
                        return {"success": True, "analyzed": False, "reason": "Duplicate job"}

                from app.models import Job
                job = Job(
                    message_id=message.id,
                    channel_id=message.channel_id,
                    channel_name=channel.name if channel else None,
                    source_type="telegram",
                    confidence=confidence,
                    translated_text=translated_text,
                    title=title,
                    company=company,
                    company_link=job_data.get("company_link"),
                    location=location,
                    is_remote=is_remote,
                    role_type=job_data.get("role_type"),
                    skills=job_data.get("skills", []),
                    contact=contact,
                    contact_type=contact_type,
                    summary=job_data.get("summary"),
                )
                db.add(job)
                message.analysis_status = "analyzed"
                await db.commit()
                return {"success": True, "analyzed": True, "type": "job"}

            elif category == "personal_info" and result.get("personal_info"):
                pi_data = result.get("personal_info", {})

                contact = _to_str(pi_data.get("contact"))
                contact_type = _to_str(pi_data.get("contact_type"))

                portfolio = _to_str(pi_data.get("portfolio"))
                github = _to_str(pi_data.get("github"))
                linkedin = _to_str(pi_data.get("linkedin"))

                name = pi_data.get("name")
                if name:
                    conditions = [Developer.name == name]
                    if contact:
                        conditions.append(Developer.contact == contact)
                    if github:
                        conditions.append(Developer.github == github)
                    if linkedin:
                        conditions.append(Developer.linkedin == linkedin)

                    if len(conditions) >= 2:
                        existing_dev_result = await db.execute(
                            select(Developer).filter(*conditions)
                        )
                        existing_dev = existing_dev_result.scalar_one_or_none()
                        if existing_dev:
                            message.analysis_status = "skipped"
                            await db.commit()
                            return {"success": True, "analyzed": False, "reason": "Duplicate developer"}

                developer = Developer(
                    message_id=message.id,
                    channel_id=message.channel_id,
                    confidence=confidence,
                    translated_text=translated_text,
                    name=name,
                    skills=pi_data.get("skills", []),
                    experience=pi_data.get("experience"),
                    portfolio=portfolio,
                    github=github,
                    linkedin=linkedin,
                    contact=contact,
                    contact_type=contact_type,
                    looking_for_work=pi_data.get("looking_for_work"),
                    summary=pi_data.get("summary"),
                )
                db.add(developer)
                message.analysis_status = "analyzed"
                await db.commit()
                return {"success": True, "analyzed": True, "type": "developer"}
            else:
                message.analysis_status = "skipped"
                await db.commit()
                return {"success": True, "analyzed": False, "reason": "No relevant category"}

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to re-analyze message: {str(e)}")

    @app.post("/api/stop-analyze")
    async def stop_analyze(
        channel_id: int = Query(..., description="Channel ID to stop analysis for"),
        db: AsyncSession = Depends(get_db)
    ):
        """Stop the current analysis process for a specific channel."""
        try:
            from app.tasks import stop_analysis, analysis_stop_events
            from app.models import Operation
            from sqlalchemy import select
            import logging
            logger = logging.getLogger(__name__)

            logger.info(f"Stop analysis requested for channel_id={channel_id}")
            logger.info(f"Current stop events in memory: {list(analysis_stop_events.keys())}")

            # First check in-memory (fast path)
            if channel_id in analysis_stop_events:
                await stop_analysis(channel_id)
                logger.info(f"Stop signal sent via memory for channel_id={channel_id}")

                # Also update any running operation in database
                result = await db.execute(
                    select(Operation).filter(
                        Operation.channel_id == channel_id,
                        Operation.status == "running"
                    )
                )
                operation = result.scalar_one_or_none()
                if operation:
                    operation.status = "stopped"
                    operation.completed_at = datetime.utcnow()
                    await db.commit()

                return {"success": True, "message": "Stop signal sent"}

            # Fallback: Check database for running operations (cross-process support)
            result = await db.execute(
                select(Operation).filter(
                    Operation.channel_id == channel_id,
                    Operation.status == "running"
                )
            )
            operation = result.scalar_one_or_none()

            if operation:
                # Mark operation as stopped in database
                operation.status = "stopped"
                operation.completed_at = datetime.utcnow()
                await db.commit()
                logger.info(f"Operation marked as stopped in database for channel_id={channel_id}")

                # Try to stop via memory if available
                if channel_id in analysis_stop_events:
                    await stop_analysis(channel_id)
                    logger.info(f"Also sent memory signal for channel_id={channel_id}")

                return {"success": True, "message": "Stop signal sent (cross-process)"}

            logger.warning(f"No active analysis found for channel_id={channel_id}")
            return {"success": False, "message": "No active analysis found for this channel"}

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to stop analysis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to stop analysis: {str(e)}")

    @app.post("/api/cron/start")
    async def start_cron():
        """Start the continuous scanner cron job."""
        try:
            from app.tasks import start_cron_task, broadcast_progress
            started = await start_cron_task()
            if started:
                await broadcast_progress("cron_status", {"running": True})
                return {"success": True, "message": "Cron job started"}
            else:
                return {"success": False, "message": "Cron job is already running"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start cron: {str(e)}")

    @app.post("/api/cron/stop")
    async def stop_cron():
        """Stop the continuous scanner cron job."""
        try:
            from app.tasks import stop_cron_task, broadcast_progress
            stopped = await stop_cron_task()
            if stopped:
                await broadcast_progress("cron_status", {"running": False})
                return {"success": True, "message": "Cron job stopped"}
            else:
                return {"success": False, "message": "Cron job is not running"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop cron: {str(e)}")

    class BulkStopRequest(BaseModel):
        operation_id: str

    @app.post("/api/bulk/stop")
    async def stop_bulk_operation(request: BulkStopRequest):
        """Stop a bulk operation (analyze-all or fetch-analyze-all)."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"[BULK STOP] Received stop request for operation: {request.operation_id}")
            from app.tasks import stop_bulk_operation as tasks_stop_bulk_operation
            await tasks_stop_bulk_operation(request.operation_id)
            logger.info(f"[BULK STOP] Stop signal set for operation: {request.operation_id}")
            return {"success": True, "message": f"Stop signal sent for operation {request.operation_id}"}
        except Exception as e:
            logger.error(f"[BULK STOP] Failed to stop bulk operation {request.operation_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to stop bulk operation: {str(e)}")

    @app.get("/api/cron/status")
    async def cron_status():
        """Get the current status of the cron job."""
        try:
            from app.tasks import is_cron_running
            running = is_cron_running()
            return {"success": True, "running": running}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get cron status: {str(e)}")

    @app.get("/api/auto-analyze")
    async def get_auto_analyze_status():
        """Get the current auto-analyze preference."""
        from app.tasks import get_auto_analyze
        return {"success": True, "enabled": get_auto_analyze()}

    @app.post("/api/auto-analyze")
    async def set_auto_analyze_status(enabled: bool = Query(..., description="Enable or disable auto-analyze")):
        """Set the global auto-analyze preference."""
        from app.tasks import set_auto_analyze
        set_auto_analyze(enabled)
        return {"success": True, "enabled": enabled}

    @app.post("/api/cleanup/old-messages")
    async def cleanup_old_messages(days: int = Query(30, description="Delete messages older than this many days"), db: AsyncSession = Depends(get_db)):
        """Delete messages older than specified days (and their associated jobs). Developers are kept."""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Count messages to be deleted
            result = await db.execute(
                select(func.count(Message.id)).filter(Message.date < cutoff_date)
            )
            count = result.scalar()
            
            if count == 0:
                return {"success": True, "deleted": 0, "message": "No old messages found"}
            
            # Delete messages (cascade will delete jobs, but not developers)
            result = await db.execute(
                select(Message).filter(Message.date < cutoff_date)
            )
            messages_to_delete = result.scalars().all()
            
            for msg in messages_to_delete:
                await db.delete(msg)
            
            await db.commit()
            
            return {
                "success": True,
                "deleted": count,
                "message": f"Deleted {count} messages older than {days} days (and their associated jobs)"
            }
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to cleanup old messages: {str(e)}")

    @app.get("/api/telegram-dialogs")
    async def get_telegram_dialogs(account_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
        """Get available Telegram dialogs (channels/groups), excluding those already in database."""
        try:
            import asyncio
            from telegram_processor import TelegramClientManager, get_dialogs
            from app.models import TelegramAccount
            from app.tasks import get_fetch_lock

            # Get Telegram account from database
            if account_id:
                result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
                account = result.scalar_one_or_none()
                if not account:
                    raise HTTPException(status_code=404, detail="Telegram account not found")
            else:
                # Get first active account
                result = await db.execute(
                    select(TelegramAccount).filter(TelegramAccount.is_active == True, TelegramAccount.is_authenticated == True)
                )
                account = result.scalars().first()
                if not account:
                    raise HTTPException(
                        status_code=400,
                        detail="No active authenticated Telegram account found. Please add a Telegram account in Settings > Telegram Accounts and authenticate it first."
                    )

            # Get existing channel usernames from database
            result = await db.execute(select(Channel.username))
            existing_usernames = set(row[0].lower() for row in result.all() if row[0])

            # Create Telegram client with account credentials
            telegram_manager = TelegramClientManager(
                api_id=account.api_id,
                api_hash=account.api_hash,
                phone_number=account.phone_number,
                session_name=account.session_name,
            )

            # Use per-account lock to prevent SQLite session conflicts
            fetch_lock = await get_fetch_lock(account.id)
            
            async with fetch_lock:
                await telegram_manager.connect()
                try:
                    dialogs = await get_dialogs(telegram_manager.client)
                finally:
                    await telegram_manager.disconnect()

            # Filter out existing channels
            filtered_dialogs = []
            for dialog in dialogs:
                username = (dialog.get('username') or '').lower()
                username_with_at = username if username.startswith('@') else f'@{username}'
                if username and (username not in existing_usernames and username_with_at not in existing_usernames):
                    filtered_dialogs.append(dialog)

            return {"success": True, "dialogs": filtered_dialogs}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get dialogs: {str(e)}")

    class StartListenerRequest(BaseModel):
        channel_usernames: list[str]
        auto_analyze: bool = False
        telegram_account_id: Optional[int] = None

    @app.post("/api/listener/start")
    async def start_listener(request: StartListenerRequest):
        """Start real-time Telegram message listener for specified channels."""
        try:
            from app.tasks import broadcast_progress, set_auto_analyze
            set_auto_analyze(request.auto_analyze)
            result = await start_telegram_listener(
                channel_usernames=request.channel_usernames,
                auto_analyze=request.auto_analyze,
                telegram_account_id=request.telegram_account_id
            )
            if result.get("success"):
                await broadcast_progress("listener_status", {"running": True, "account_id": result.get("account_id")})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start listener: {str(e)}")

    @app.post("/api/listener/stop")
    async def stop_listener(telegram_account_id: Optional[int] = None):
        """Stop the real-time Telegram message listener.

        Args:
            telegram_account_id: Optional account ID to stop. If None, stops all listeners.
        """
        try:
            from app.tasks import broadcast_progress
            result = await stop_telegram_listener(telegram_account_id)
            if result.get("success"):
                await broadcast_progress("listener_status", {"running": False, "account_id": telegram_account_id})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop listener: {str(e)}")

    @app.get("/api/listener/status")
    async def listener_status(telegram_account_id: Optional[int] = None):
        """Get the current status of the real-time listener(s).
        
        Args:
            telegram_account_id: Optional account ID. If None, returns status of all listeners.
        """
        from app.tasks import telegram_listener_running, telegram_listeners
        
        if telegram_account_id is not None:
            # Return status for specific account
            listener = telegram_listeners.get(telegram_account_id)
            return {
                "running": telegram_listener_running.get(telegram_account_id, False),
                "account_id": telegram_account_id,
                "listening_to": listener.listened_channels if listener else [],
            }
        else:
            # Return status for all accounts
            accounts = []
            for aid, running in telegram_listener_running.items():
                if running:
                    listener = telegram_listeners.get(aid)
                    accounts.append({
                        "account_id": aid,
                        "listening_to": listener.listened_channels if listener else [],
                    })
            return {
                "running": len(accounts) > 0,
                "accounts": accounts,
                "total_listeners": len(accounts),
            }

    class AddChannelsRequest(BaseModel):
        channel_usernames: list[str]
        telegram_account_id: Optional[int] = None

    @app.post("/api/listener/add-channels")
    async def add_channels(request: AddChannelsRequest):
        """Add channels to the running real-time listener."""
        try:
            result = await add_listener_channels(
                request.channel_usernames,
                request.telegram_account_id
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add channels: {str(e)}")

    class RemoveChannelsRequest(BaseModel):
        channel_usernames: list[str]
        telegram_account_id: Optional[int] = None

    @app.post("/api/listener/remove-channels")
    async def remove_channels(request: RemoveChannelsRequest):
        """Remove channels from the running real-time listener."""
        try:
            result = await remove_listener_channels(
                request.channel_usernames,
                request.telegram_account_id
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove channels: {str(e)}")

    @app.get("/api/listener/channels")
    async def listener_channels(telegram_account_id: Optional[int] = None):
        """Get list of channels currently being listened to."""
        try:
            result = await get_listener_channels(telegram_account_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get listener channels: {str(e)}")