"""Analyze-related API routes."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import get_db, AsyncSessionLocal
from app.models import Channel, Developer, Job, Message, Operation
from app.tasks.helpers import _to_bool
from app.tasks import (
    analyze_messages,
    broadcast_progress,
    reset_bulk_stop_event,
    is_bulk_operation_stopped,
    cleanup_bulk_stop_event,
    stop_analysis,
    analysis_stop_events,
    cleanup_stale_operations,
    _analyze_single,
    _to_str,
    _to_bool,
)

logger = logging.getLogger(__name__)


def register_analyze_action_routes(app):

    async def _analyze_channel_bg(channel_id: int):
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                channel = result.scalar_one_or_none()
                if channel:
                    channel_name = channel.username or channel.name or f"ID:{channel_id}"
                    logger.info(f"[BG TASK] Analyzing channel @{channel_name} (ID: {channel_id})")
                    analyze_result = await analyze_messages(db, channel)
                    success = analyze_result.get("success", False)
                    jobs = analyze_result.get("jobs_found", 0)
                    devs = analyze_result.get("developers_found", 0)
                    error = analyze_result.get("error", "unknown")
                    if success:
                        logger.info(f"[BG TASK] Completed analysis for @{channel_name}: {jobs} jobs, {devs} devs")
                    else:
                        logger.warning(f"[BG TASK] Analysis failed for @{channel_name}: {error}")
                else:
                    logger.warning(f"[BG TASK] Channel {channel_id} not found")
            except Exception as e:
                logger.error(f"[BG TASK] Exception during analysis for channel {channel_id}: {e}", exc_info=True)

    @app.post("/api/analyze/{channel_id}")
    async def analyze_channel(channel_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")

            pending_result = await db.execute(
                select(func.count(Message.id)).filter(Message.channel_id == channel_id, Message.analysis_status == "pending")
            )
            pending_count = pending_result.scalar() or 0
            if pending_count == 0:
                return {"success": True, "message": "No pending messages to analyze", "analyzed": 0}

            existing_op = await db.execute(
                select(Operation).filter(Operation.channel_id == channel_id, Operation.operation_type == "analyze", Operation.status == "running")
            )
            if existing_op.scalar_one_or_none():
                return {"success": False, "message": "Analysis already running for this channel"}

            background_tasks.add_task(_analyze_channel_bg, channel_id)
            return {"success": True, "message": f"Analysis started for {pending_count} pending message(s)", "analyzed": 0, "pending": pending_count}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")

    async def _run_analyze_all(channel_ids: list, operation_id: str):
        logger.info(f"[BULK ANALYZE] Starting operation {operation_id} for {len(channel_ids)} channels")
        await reset_bulk_stop_event(operation_id)
        success_count = error_count = 0
        try:
            for idx, channel_id in enumerate(channel_ids):
                if is_bulk_operation_stopped(operation_id):
                    logger.info(f"[BULK ANALYZE] Operation {operation_id} stopped at channel {idx+1}/{len(channel_ids)}")
                    break
                async with AsyncSessionLocal() as db:
                    try:
                        db.sync_session.expire_on_commit = False
                        result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                        channel = result.scalar_one_or_none()
                        if channel:
                            analyze_result = await analyze_messages(db, channel, bulk_operation_id=operation_id)
                            if analyze_result.get("success"):
                                success_count += 1
                            else:
                                error_count += 1
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
        await cleanup_stale_operations()
        channels_result = await db.execute(
            select(Channel.id).join(Message, Message.channel_id == Channel.id)
            .filter(Message.analysis_status == "pending").group_by(Channel.id)
        )
        channel_ids = [row[0] for row in channels_result.all()]
        if not channel_ids:
            return {"success": True, "message": "No channels with pending messages found"}
        operation_id = f"analyze-all-{uuid.uuid4().hex[:8]}"
        background_tasks.add_task(_run_analyze_all, channel_ids, operation_id)
        return {"success": True, "message": f"Analysis started for {len(channel_ids)} channel(s)", "channels": len(channel_ids), "operation_id": operation_id}

    @app.post("/api/reanalyze")
    async def reanalyze_messages(db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(select(Message).filter(Message.needs_reanalysis == True))
            messages = result.scalars().all()
            reanalyzed = 0
            for message in messages:
                try:
                    channel_result = await db.execute(select(Channel).filter(Channel.id == message.channel_id))
                    channel = channel_result.scalar_one_or_none()
                    from services.ollama_service import get_analyzer
                    analyzer = get_analyzer()
                    analysis = await analyzer.analyze_message(message.text)

                    if analysis.get("category") == "job_posting":
                        job_data = analysis.get("job_posting", {})
                        job_result = await db.execute(select(Job).filter(Job.message_id == message.id))
                        job = job_result.scalar_one_or_none()
                        summary_text = job_data.get("summary") or ""
                        title = job_data.get("title") or (summary_text.split(".")[0].strip()[:200] if summary_text else None)
                        if job:
                            job.title = title
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
                            db.add(Job(
                                message_id=message.id,
                                channel_id=message.channel_id,
                                channel_name=channel.name if channel else None,
                                source_type="telegram",
                                title=title,
                                company=job_data.get("company"),
                                location=job_data.get("location"),
                                is_remote=_to_bool(job_data.get("is_remote")),
                                role_type=_to_str(job_data.get("role_type")),
                                skills=job_data.get("skills"),
                                contact=job_data.get("contact"),
                                summary=job_data.get("summary"),
                                translated_text=analysis.get("translated_text"),
                                confidence=analysis.get("confidence"),
                            ))
                            message.needs_reanalysis = False

                    elif analysis.get("category") == "personal_info":
                        dev_data = analysis.get("personal_info", {})
                        dev_result = await db.execute(select(Developer).filter(Developer.message_id == message.id))
                        dev = dev_result.scalar_one_or_none()
                        if dev:
                            dev.name = dev_data.get("name")
                            dev.skills = dev_data.get("skills")
                            dev.experience = dev_data.get("experience")
                            dev.contact = dev_data.get("contact")
                            dev.looking_for_work = _to_bool(dev_data.get("looking_for_work"))
                            dev.summary = dev_data.get("summary")
                            dev.translated_text = analysis.get("translated_text")
                            dev.confidence = analysis.get("confidence")
                            dev.analyzed_at = datetime.utcnow()
                            message.needs_reanalysis = False
                        else:
                            db.add(Developer(
                                message_id=message.id,
                                channel_id=message.channel_id,
                                name=dev_data.get("name"),
                                skills=dev_data.get("skills"),
                                experience=dev_data.get("experience"),
                                contact=dev_data.get("contact"),
                                looking_for_work=_to_bool(dev_data.get("looking_for_work")),
                                summary=dev_data.get("summary"),
                                translated_text=analysis.get("translated_text"),
                                confidence=analysis.get("confidence"),
                            ))
                            message.needs_reanalysis = False
                    else:
                        message.needs_reanalysis = False

                    reanalyzed += 1
                    await db.commit()
                except Exception:
                    await db.rollback()
                    continue
            return {"success": True, "reanalyzed": reanalyzed}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reanalyze: {str(e)}")

    async def _run_reanalyze_skipped(channel_ids: list, operation_id: str):
        logger.info(f"[REANALYZE SKIPPED] Starting operation {operation_id} for {len(channel_ids)} channels")
        await reset_bulk_stop_event(operation_id)
        success_count = error_count = 0
        try:
            for idx, channel_id in enumerate(channel_ids):
                if is_bulk_operation_stopped(operation_id):
                    logger.info(f"[REANALYZE SKIPPED] Operation {operation_id} stopped at channel {idx+1}/{len(channel_ids)}")
                    break
                async with AsyncSessionLocal() as channel_db:
                    try:
                        channel_result = await channel_db.execute(select(Channel).filter(Channel.id == channel_id))
                        channel = channel_result.scalar_one_or_none()
                        if not channel:
                            continue
                        await channel_db.execute(
                            Message.__table__.update()
                            .where((Message.channel_id == channel_id) & (Message.analysis_status == "skipped") & (Message.is_manual_skip == False))
                            .values(analysis_status="pending")
                        )
                        await channel_db.commit()
                        result = await analyze_messages(channel_db, channel, bulk_operation_id=operation_id)
                        if result.get("success"):
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(f"[REANALYZE SKIPPED] Exception in channel {channel_id}: {e}", exc_info=True)
            logger.info(f"[REANALYZE SKIPPED] Operation {operation_id} complete: {success_count} success, {error_count} errors")
        finally:
            cleanup_bulk_stop_event(operation_id)

    @app.post("/api/reanalyze-skipped")
    async def reanalyze_skipped_messages(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(
                select(Message.channel_id, func.count(Message.id).label("count"))
                .filter(Message.analysis_status == "skipped", Message.is_manual_skip == False).group_by(Message.channel_id)
            )
            channel_counts = result.all()
            if not channel_counts:
                return {"success": True, "message": "No skipped messages to re-analyze"}
            channel_ids = [row[0] for row in channel_counts]
            total_skipped = sum(row[1] for row in channel_counts)
            operation_id = f"reanalyze-skipped-{uuid.uuid4().hex[:8]}"
            background_tasks.add_task(_run_reanalyze_skipped, channel_ids, operation_id)
            return {"success": True, "message": f"Re-analysis started for {total_skipped} skipped message(s) across {len(channel_ids)} channel(s)", "operation_id": operation_id, "total_skipped": total_skipped, "channels": len(channel_ids)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to re-analyze skipped messages: {str(e)}")

    @app.post("/api/reanalyze-message/{message_id}")
    async def reanalyze_single_message(message_id: int, db: AsyncSession = Depends(get_db)):
        try:
            from services.ollama_service import get_analyzer, is_ollama_available
            if not await is_ollama_available():
                raise HTTPException(status_code=500, detail="Ollama not available")

            result = await db.execute(select(Message).filter(Message.id == message_id))
            message = result.scalar_one_or_none()
            if not message:
                raise HTTPException(status_code=404, detail="Message not found")

            channel_result = await db.execute(select(Channel).filter(Channel.id == message.channel_id))
            channel = channel_result.scalar_one_or_none()
            message.analysis_status = "pending"
            await db.commit()

            analyzer = get_analyzer()
            channel_username = channel.username if channel else "unknown"
            message, result_data, error = await _analyze_single(analyzer, message, channel_username)

            if error:
                message.analysis_status = "failed"
                await db.commit()
                raise HTTPException(status_code=500, detail=f"Analysis failed: {str(error)}")

            if not result_data or result_data.get("category") == "other":
                message.analysis_status = "skipped"
                await db.commit()
                return {"success": True, "analyzed": False, "reason": "No relevant content found"}

            category = result_data.get("category", "other")
            confidence = result_data.get("confidence")
            translated_text = result_data.get("translated_text")

            if category == "job_posting" and result_data.get("job_posting"):
                job_data = result_data.get("job_posting", {})
                is_remote = _to_bool(job_data.get("is_remote"))
                if is_remote is False:
                    message.analysis_status = "skipped"
                    await db.commit()
                    return {"success": True, "analyzed": False, "reason": "On-site job filtered"}

                location = job_data.get("location")
                if isinstance(location, list):
                    location = ", ".join(location)

                summary_str = job_data.get("summary") or ""
                title = job_data.get("title") or (summary_str.split(".")[0].strip()[:200] if summary_str else None)
                company = job_data.get("company")
                if title and company:
                    existing_job_result = await db.execute(select(Job).filter(Job.title == title, Job.company == company))
                    if existing_job_result.scalar_one_or_none():
                        message.analysis_status = "skipped"
                        await db.commit()
                        return {"success": True, "analyzed": False, "reason": "Duplicate job"}

                role_type = job_data.get("role_type")
                if isinstance(role_type, list):
                    role_type = ", ".join(role_type)

                contact = job_data.get("contact")
                if isinstance(contact, list):
                    contact = ", ".join(contact)
                contact_type = job_data.get("contact_type")
                if isinstance(contact_type, list):
                    contact_type = ", ".join(contact_type)

                db.add(Job(
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
                ))
                message.analysis_status = "analyzed"
                await db.commit()
                return {"success": True, "analyzed": True, "type": "job"}

            elif category == "personal_info" and result_data.get("personal_info"):
                pi_data = result_data.get("personal_info", {})
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
                        existing_dev_result = await db.execute(select(Developer).filter(*conditions))
                        if existing_dev_result.scalar_one_or_none():
                            message.analysis_status = "skipped"
                            await db.commit()
                            return {"success": True, "analyzed": False, "reason": "Duplicate developer"}

                db.add(Developer(
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
                    looking_for_work=_to_bool(pi_data.get("looking_for_work")),
                    summary=pi_data.get("summary"),
                ))
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
    async def stop_analyze(channel_id: int = Query(..., description="Channel ID to stop analysis for"), db: AsyncSession = Depends(get_db)):
        try:
            logger.info(f"Stop analysis requested for channel_id={channel_id}")
            logger.info(f"Current stop events in memory: {list(analysis_stop_events.keys())}")

            if channel_id in analysis_stop_events:
                await stop_analysis(channel_id)
                result = await db.execute(select(Operation).filter(Operation.channel_id == channel_id, Operation.status == "running"))
                operation = result.scalar_one_or_none()
                if operation:
                    operation.status = "stopped"
                    operation.completed_at = datetime.utcnow()
                    await db.commit()
                return {"success": True, "message": "Stop signal sent"}

            result = await db.execute(select(Operation).filter(Operation.channel_id == channel_id, Operation.status == "running"))
            operation = result.scalar_one_or_none()
            if operation:
                operation.status = "stopped"
                operation.completed_at = datetime.utcnow()
                await db.commit()
                if channel_id in analysis_stop_events:
                    await stop_analysis(channel_id)
                return {"success": True, "message": "Stop signal sent (cross-process)"}

            logger.warning(f"No active analysis found for channel_id={channel_id}")
            return {"success": False, "message": "No active analysis found for this channel"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop analysis: {str(e)}")

    class BulkStopRequest(BaseModel):
        operation_id: str

    @app.post("/api/bulk/stop")
    async def stop_bulk(request: BulkStopRequest):
        try:
            from app.tasks import stop_bulk_operation as tasks_stop_bulk
            await tasks_stop_bulk(request.operation_id)
            return {"success": True, "message": f"Stop signal sent for operation {request.operation_id}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop bulk operation: {str(e)}")

    @app.post("/api/cleanup/old-messages")
    async def cleanup_old_messages(days: int = Query(30, description="Delete messages older than this many days"), db: AsyncSession = Depends(get_db)):
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await db.execute(select(func.count(Message.id)).filter(Message.date < cutoff_date))
            count = result.scalar()
            if count == 0:
                return {"success": True, "deleted": 0, "message": "No old messages found"}
            result = await db.execute(select(Message).filter(Message.date < cutoff_date))
            for msg in result.scalars().all():
                await db.delete(msg)
            await db.commit()
            return {"success": True, "deleted": count, "message": f"Deleted {count} messages older than {days} days"}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to cleanup old messages: {str(e)}")
