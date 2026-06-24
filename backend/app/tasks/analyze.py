"""Analyze Telegram messages and website posts with AI."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisRun, Channel, Developer, Job, Message, WebsiteSource
from services.ollama_service import get_analyzer, is_ollama_available, should_analyze_message
from app.tasks.stop_events import (
    reset_stop_event,
    cleanup_stop_event,
    is_analysis_stopped,
    is_bulk_operation_stopped,
    reset_website_stop_event,
    cleanup_website_stop_event,
    is_website_operation_stopped,
)
from app.tasks.operations import (
    broadcast_progress,
    broadcast_stats_update,
    create_operation,
    update_operation,
)
from app.tasks.helpers import _to_str, _to_bool, _resolve_contact

logger = logging.getLogger(__name__)


async def _analyze_single(analyzer, message, channel_username: str, msg_index: int = 0, total_messages: int = 0):
    import asyncio
    import time
    start_time = time.time()
    msg_preview = message.text[:50] if message.text else "[no text]"

    await broadcast_progress("analyzing_message", {
        "channel": channel_username,
        "message_id": message.id,
        "message_text": message.text[:200] if message.text else "",
        "message_preview": msg_preview,
        "analyzed": msg_index,
        "total": total_messages,
        "total_messages": total_messages,
    })

    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            text_to_analyze = getattr(message, 'analysis_text', None) or message.text
            result = await asyncio.wait_for(
                analyzer.analyze_message(text_to_analyze),
                timeout=300,
            )
            return message, result, None
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[ANALYZE RETRY] Timeout on attempt {attempt + 1}/{max_retries}, retrying in {delay}s")
                await asyncio.sleep(delay)
            else:
                return message, None, Exception("Analysis timeout after 300s")
        except Exception as e:
            error_str = str(e).lower()
            is_transient = any(k in error_str for k in [
                'connection', 'timeout', 'network', 'temporary', 'unavailable',
                '503', '502', '504', 'econnrefused', 'econnreset',
            ])
            if is_transient and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[ANALYZE RETRY] Transient error on attempt {attempt + 1}/{max_retries}: {e}, retrying in {delay}s")
                await asyncio.sleep(delay)
            else:
                elapsed = time.time() - start_time
                logger.error(f"[ANALYZE MSG ERROR] Channel: {channel_username} | Msg: {msg_preview}... | Time: {elapsed:.1f}s | Error: {e}")
                return message, None, e


async def analyze_messages(
    db: AsyncSession,
    channel: Channel,
    run_id: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> dict:
    channel_id = channel.id
    channel_username = channel.username
    channel_name = channel.name

    if not await is_ollama_available():
        return {"success": False, "error": "AI provider not available (check ANALYZE_PROVIDER and related API keys)"}

    try:
        await reset_stop_event(channel_id)

        from sqlalchemy.orm import selectinload
        messages_result = await db.execute(
            select(Message).options(
                selectinload(Message.job),
                selectinload(Message.developer),
                selectinload(Message.channel),
            ).filter(
                Message.channel_id == channel_id,
                Message.analysis_status.in_(["pending", "failed"]),
            ).order_by(Message.date.desc())
        )
        messages = messages_result.scalars().all()
        total_messages = len(messages)

        operation_id = await create_operation(db, "analyze", channel, total_messages=total_messages, bulk_operation_id=bulk_operation_id)

        await broadcast_progress("analyze_start", {"channel": channel_username, "channel_id": channel_id, "operation_id": operation_id})
        await broadcast_progress("analyze_progress", {"channel": channel_username, "status": "found", "total": total_messages, "operation_id": operation_id})
        await update_operation(db, operation_id, total_messages=total_messages)

        if total_messages == 0:
            await update_operation(db, operation_id, status="completed")
            return {"success": True, "analyzed": 0, "jobs_found": 0, "developers_found": 0, "skipped": 0}

        from app.routes.settings import get_analyze_provider
        _is_nvidia = get_analyze_provider() == "nvidia"
        _NVIDIA_INTER_REQUEST_DELAY = 2.0

        analyzer = get_analyzer()

        jobs_added = devs_added = skipped_count = analyzed_count = stopped_count = 0
        total_input_tokens = total_output_tokens = 0
        message_results: list[dict] = []
        consecutive_failures = 0

        async def _process_message_result(message, result, error, msg_index):
            nonlocal jobs_added, devs_added, skipped_count, analyzed_count, consecutive_failures, total_input_tokens, total_output_tokens

            if error:
                message.analysis_status = "failed"
                message_results.append({"message_id": message.id, "status": "failed", "error": str(error)})
                logger.warning(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] FAILED | msg_id={message.id} | error={str(error)[:120]}")
                consecutive_failures += 1
                return

            if not result or result.get("category") == "other":
                await db.delete(message)
                skipped_count += 1
                message_results.append({"message_id": message.id, "status": "other"})
                logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] SKIPPED (other) | msg_id={message.id}")
                return

            usage = result.get("usage", {})
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)

            category = _to_str(result.get("category"))
            confidence = _to_str(result.get("confidence"))
            translated_text = _to_str(result.get("translated_text"))

            notification_data = {
                "message_id": message.id,
                "status": "success" if (confidence and category) else "json_cutoff",
                "category": category,
                "confidence": confidence,
            }

            if category == "job_posting":
                job_data = result.get("job_posting") or {}
                is_remote = _to_bool(job_data.get("is_remote"))
                if is_remote is False:
                    await db.delete(message)
                    skipped_count += 1
                    logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] SKIPPED (on-site) | msg_id={message.id}")
                    return

                summary_text = _to_str(job_data.get("summary"))
                title = _to_str(job_data.get("title"))
                if not title and summary_text:
                    title = summary_text.split(".")[0].strip()[:200]
                if not title and message.text:
                    clean_text = message.text.replace('<br/>', '\n').replace('<br>', '\n').replace('<p>', '\n').replace('</p>', '\n')
                    title = clean_text.split('\n')[0].strip()[:100] or None
                if not title:
                    title = f"[No Title] sender:{message.sender_username or message.sender_id or 'unknown'}"
                company = _to_str(job_data.get("company"))

                notification_data["title"] = title
                notification_data["company"] = company

                location = _to_str(job_data.get("location"))
                contact, contact_type = _resolve_contact(job_data.get("contacts"), message)

                if title and company:
                    company_link = _to_str(job_data.get("company_link"))
                    if company_link:
                        existing_job_result = await db.execute(select(Job).filter(Job.company_link == company_link))
                    else:
                        existing_job_result = await db.execute(select(Job).filter(Job.title == title, Job.company == company))
                    if existing_job_result.first():
                        await db.delete(message)
                        skipped_count += 1
                        logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] SKIPPED (duplicate job) | msg_id={message.id}")
                        return

                role_str = _to_str(job_data.get("role_type"))
                try:
                    job = Job(
                        message_id=message.id,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        source_type="telegram",
                        confidence=confidence,
                        translated_text=translated_text,
                        title=title,
                        company=company,
                        company_link=_to_str(job_data.get("company_link")),
                        location=location,
                        is_remote=is_remote,
                        role_type=role_str,
                        skills=job_data.get("skills"),
                        contact=contact,
                        contact_type=contact_type,
                        summary=_to_str(job_data.get("summary")),
                    )
                    db.add(job)
                    await db.flush()
                    await db.refresh(job)
                    jobs_added += 1
                    message.analysis_status = "analyzed"
                    logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] ✓ JOB SAVED | msg_id={message.id} | title={title[:60]}")
                    await broadcast_progress("new_job", {
                        "job_id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "channel": channel_name,
                        "is_remote": job.is_remote,
                        "location": job.location,
                        "role_type": job.role_type,
                    })
                except Exception as e:
                    skipped_count += 1
                    message.analysis_status = "failed"
                    logger.error(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] FAILED (db_error job) | msg_id={message.id} | error={str(e)[:120]}")
                    await db.rollback()

            elif category == "personal_info":
                pi_data = result.get("personal_info") or {}
                name = _to_str(pi_data.get("name"))
                contact, contact_type = _resolve_contact(pi_data.get("contacts"), message)
                portfolio = _to_str(pi_data.get("portfolio"))
                github = _to_str(pi_data.get("github"))
                linkedin = _to_str(pi_data.get("linkedin"))

                if not name:
                    name = message.sender_username or f"sender:{message.sender_id or 'unknown'}"

                notification_data["name"] = name

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
                        if existing_dev_result.first():
                            await db.delete(message)
                            skipped_count += 1
                            logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] SKIPPED (duplicate dev) | msg_id={message.id}")
                            return

                exp_val = pi_data.get("experience")
                exp_str = "\n".join(str(i) for i in exp_val) if isinstance(exp_val, list) else (str(exp_val) if exp_val else None)

                try:
                    developer = Developer(
                        message_id=message.id,
                        channel_id=channel_id,
                        confidence=confidence,
                        translated_text=translated_text,
                        name=name,
                        skills=pi_data.get("skills"),
                        experience=exp_str,
                        portfolio=portfolio,
                        github=github,
                        linkedin=linkedin,
                        contact=contact,
                        contact_type=contact_type,
                        looking_for_work=pi_data.get("looking_for_work"),
                        summary=_to_str(pi_data.get("summary")),
                    )
                    db.add(developer)
                    devs_added += 1
                    message.analysis_status = "analyzed"
                    logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] ✓ DEV SAVED | msg_id={message.id} | name={name[:60]}")
                except Exception as e:
                    skipped_count += 1
                    message.analysis_status = "failed"
                    logger.error(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] FAILED (db_error dev) | msg_id={message.id} | error={str(e)[:120]}")
                    await db.rollback()

            else:
                await db.delete(message)
                skipped_count += 1

            message_results.append(notification_data)
            analyzed_count += 1

            last_result = message_results[-1] if message_results else {}
            await broadcast_progress("analyze_progress", {
                "channel": channel_username,
                "channel_id": channel_id,
                "current": msg_index + 1,
                "total": total_messages,
                "analyzed": analyzed_count,
                "total_messages": total_messages,
                "jobs": jobs_added,
                "developers": devs_added,
                "operation_id": operation_id,
                "tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens,
                },
                "message_results": [last_result] if last_result else [],
            })

            try:
                await update_operation(db, operation_id, current=msg_index + 1, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)
            except Exception:
                pass

            if _is_nvidia:
                await asyncio.sleep(_NVIDIA_INTER_REQUEST_DELAY)

        OLLAMA_CONCURRENCY = int(os.getenv("OLLAMA_MAX_CONCURRENT", "3"))
        if OLLAMA_CONCURRENCY < 1:
            OLLAMA_CONCURRENCY = 1

        if _is_nvidia:
            for msg_index, msg in enumerate(messages):
                if is_analysis_stopped(channel_id):
                    stopped_count = total_messages - msg_index
                    break
                if bulk_operation_id and is_bulk_operation_stopped(bulk_operation_id):
                    stopped_count = total_messages - msg_index
                    break

                if not msg.text or not should_analyze_message(msg.text):
                    await db.delete(msg)
                    skipped_count += 1
                    logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] SKIPPED (pre-filter) | msg_id={msg.id}")
                    continue

                message, result, error = await _analyze_single(analyzer, msg, channel_username, msg_index, total_messages)
                await _process_message_result(message, result, error, msg_index)

                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
        else:
            for chunk_start in range(0, total_messages, OLLAMA_CONCURRENCY):
                chunk = messages[chunk_start:chunk_start + OLLAMA_CONCURRENCY]
                to_analyze = []

                for idx, msg in enumerate(chunk):
                    msg_index = chunk_start + idx

                    if is_analysis_stopped(channel_id):
                        stopped_count = total_messages - msg_index
                        break
                    if bulk_operation_id and is_bulk_operation_stopped(bulk_operation_id):
                        stopped_count = total_messages - msg_index
                        break

                    if not msg.text or not should_analyze_message(msg.text):
                        await db.delete(msg)
                        skipped_count += 1
                        logger.info(f"[ANALYZE] [{channel_username}] [{msg_index+1}/{total_messages}] SKIPPED (pre-filter) | msg_id={msg.id}")
                        continue

                    to_analyze.append((msg_index, msg))

                if stopped_count > 0:
                    break

                if to_analyze:
                    tasks = [
                        _analyze_single(analyzer, msg, channel_username, msg_index, total_messages)
                        for msg_index, msg in to_analyze
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for (msg_index, msg), item in zip(to_analyze, results):
                        if isinstance(item, Exception):
                            message, result, error = msg, None, item
                        else:
                            message, result, error = item
                        await _process_message_result(message, result, error, msg_index)

                try:
                    await db.commit()
                except Exception:
                    await db.rollback()

        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            return {
                "success": True,
                "jobs_found": jobs_added,
                "developers_found": devs_added,
                "analyzed": analyzed_count,
                "stopped": stopped_count > 0,
                "remaining": stopped_count,
                "warning": f"Commit failed: {str(e)[:100]}",
            }

        if run_id:
            try:
                run_result = await db.execute(select(AnalysisRun).filter(AnalysisRun.id == run_id))
                run = run_result.scalar_one_or_none()
                if run:
                    run.messages_analyzed += analyzed_count
                    run.jobs_found += jobs_added
                    await db.commit()
            except Exception:
                await db.rollback()

        status = "stopped" if stopped_count > 0 else "completed"
        failed_count = sum(1 for r in message_results if r.get("status") in ["failed", "db_error"])
        logger.info(
            f"[ANALYZE] [{channel_username}] ✓ COMPLETE | total={total_messages} | "
            f"analyzed={analyzed_count} | jobs={jobs_added} | devs={devs_added} | "
            f"skipped={skipped_count} | failed={failed_count} | stopped={stopped_count} | "
            f"status={status} | tokens: in={total_input_tokens} out={total_output_tokens}"
        )
        await broadcast_progress("analyze_complete", {
            "channel": channel_username,
            "channel_id": channel_id,
            "analyzed": analyzed_count,
            "jobs": jobs_added,
            "developers": devs_added,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
            "operation_id": operation_id,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
        })
        await update_operation(db, operation_id, status=status, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)
        await broadcast_stats_update(db)

        return {
            "success": True,
            "analyzed": analyzed_count,
            "jobs_found": jobs_added,
            "developers_found": devs_added,
            "skipped": skipped_count,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
        }

    except Exception as e:
        await db.rollback()
        await update_operation(db, operation_id, status="error", error_message=str(e))
        await broadcast_progress("error", {
            "channel": channel_username,
            "channel_id": channel_id,
            "operation_id": operation_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}

    finally:
        await cleanup_stop_event(channel_id)


async def analyze_website_posts(
    db: AsyncSession,
    website_source: WebsiteSource,
    bulk_operation_id: Optional[str] = None,
) -> dict:
    source_id = website_source.id
    source_name = website_source.name
    source_url = website_source.url
    custom_prompt = website_source.extraction_prompt
    site_type = website_source.site_type

    if not await is_ollama_available():
        return {"success": False, "error": "AI provider not available (check ANALYZE_PROVIDER and related API keys)"}

    try:
        from sqlalchemy.orm import selectinload
        messages_result = await db.execute(
            select(Message).options(
                selectinload(Message.job),
                selectinload(Message.developer)
            ).filter(
                Message.website_source_id == source_id,
                Message.analysis_status == "pending",
            ).order_by(Message.date.desc())
        )
        messages = messages_result.scalars().all()
        total_messages = len(messages)

        operation_id = await create_operation(db, "analyze", None, total_messages=total_messages, bulk_operation_id=bulk_operation_id)
        await update_operation(db, operation_id, channel_username=source_name, total_messages=total_messages)

        await reset_website_stop_event(source_id)

        await broadcast_progress("analyze_start", {
            "channel": source_name,
            "channel_id": source_id,
            "operation_id": operation_id,
        })

        if total_messages == 0:
            await update_operation(db, operation_id, status="completed")
            await cleanup_website_stop_event(source_id)
            return {"success": True, "analyzed": 0, "jobs_found": 0, "developers_found": 0, "skipped": 0}

        from web_crawler import Extractor
        extractor = Extractor()

        jobs_added = devs_added = skipped_count = analyzed_count = stopped_count = 0
        batch_size = 1
        total_batches = (total_messages + batch_size - 1) // batch_size
        total_input_tokens = total_output_tokens = 0
        consecutive_failures = 0

        for batch_num in range(total_batches):
            if is_website_operation_stopped(source_id):
                stopped_count = total_messages - (batch_num * batch_size)
                break

            batch_start = batch_num * batch_size
            batch_end = min(batch_start + batch_size, total_messages)
            filtered_messages = messages[batch_start:batch_end]

            for message in filtered_messages:
                message_id = message.id
                try:
                    msg_preview = (message.text or '')[:120].replace('\n', ' ')
                except Exception as e:
                    logger.error(f"[ANALYZE WEBSITE] [{source_name}] [{batch_num+1}/{total_batches}] FAILED (load) | msg_id={message_id} | error={e}")
                    await db.rollback()
                    continue

                await broadcast_progress("analyzing_message", {
                    "channel": source_name,
                    "message_id": message_id,
                    "message_text": (message.text or "")[:200],
                    "message_preview": msg_preview,
                })

                try:
                    extracted_data, usage = await extractor.extract(
                        message.text,
                        source_url,
                        custom_prompt=custom_prompt,
                        site_type=site_type,
                    )
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)

                    jobs_to_process = extracted_data.job_postings[:1] if len(extracted_data.job_postings) > 1 else extracted_data.job_postings

                    msg_job_added = 0
                    for job in jobs_to_process:
                        if job.url:
                            existing_job = await db.execute(select(Job).filter(Job.company_link == job.url))
                            if existing_job.scalars().first():
                                continue
                        existing_job = await db.execute(select(Job).filter(Job.message_id == message_id))
                        if existing_job.scalars().first():
                            continue

                        job_obj = Job(
                            message_id=message_id,
                            website_source_id=source_id,
                            channel_name=source_name,
                            source_type="website",
                            title=job.title or "Unknown",
                            company=job.company or "Unknown",
                            location=job.location,
                            is_remote=job.is_remote,
                            company_link=job.url,
                            summary=job.requirements,
                        )
                        db.add(job_obj)
                        await db.flush()
                        await db.refresh(job_obj)
                        jobs_added += 1
                        msg_job_added += 1
                        await broadcast_progress("new_job", {
                            "job_id": job_obj.id,
                            "title": job_obj.title,
                            "company": job_obj.company,
                            "channel": source_name,
                            "is_remote": job_obj.is_remote,
                            "location": job_obj.location,
                            "role_type": job_obj.role_type,
                        })

                    msg_dev_added = 0
                    if extracted_data.developer_info:
                        dev = extracted_data.developer_info
                        conditions = [Developer.name == dev.team_name]
                        portfolio = dev.open_source_links[0] if dev.open_source_links else None
                        if portfolio:
                            conditions.append(Developer.portfolio == portfolio)
                        if len(conditions) >= 2:
                            existing_dev = await db.execute(select(Developer).filter(*conditions))
                            if existing_dev.first():
                                continue
                        existing_dev = await db.execute(
                            select(Developer).filter(
                                Developer.website_source_id == source_id,
                                Developer.name == dev.team_name
                            )
                        )
                        if existing_dev.first():
                            continue

                        dev_obj = Developer(
                            website_source_id=source_id,
                            name=dev.team_name,
                            skills=dev.tech_stack,
                            portfolio=portfolio,
                            summary=dev.description,
                        )
                        db.add(dev_obj)
                        devs_added += 1
                        msg_dev_added += 1

                    if msg_job_added == 0 and msg_dev_added == 0:
                        await db.delete(message)
                        logger.info(f"[ANALYZE WEBSITE] [{source_name}] [{batch_num+1}/{total_batches}] SKIPPED (no extract) | msg_id={message_id}")
                    else:
                        message.analysis_status = "analyzed"
                        analyzed_count += 1
                        logger.info(f"[ANALYZE WEBSITE] [{source_name}] [{batch_num+1}/{total_batches}] ✓ ANALYZED | msg_id={message_id} | jobs={msg_job_added} | devs={msg_dev_added}")

                    await broadcast_progress("analyze_progress", {
                        "channel": source_name,
                        "channel_id": source_id,
                        "analyzed": analyzed_count,
                        "total_messages": total_messages,
                        "jobs": jobs_added,
                        "developers": devs_added,
                        "operation_id": operation_id,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens,
                    })

                except Exception as e:
                    logger.error(f"[ANALYZE WEBSITE] [{source_name}] [{batch_num+1}/{total_batches}] FAILED | msg_id={message_id} | error={str(e)[:120]}")
                    await db.rollback()
                    message.analysis_status = "failed"
                    continue

            await broadcast_progress("analyze_progress", {
                "channel": source_name,
                "channel_id": source_id,
                "current": batch_num + 1,
                "total": total_batches,
                "analyzed": analyzed_count,
                "total_messages": total_messages,
                "jobs": jobs_added,
                "developers": devs_added,
                "operation_id": operation_id,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
            })

            try:
                await update_operation(db, operation_id, current=batch_num + 1, analyzed=analyzed_count, jobs_found=jobs_added, developers_found=devs_added)
            except Exception:
                pass

            try:
                await db.commit()
            except Exception:
                await db.rollback()

        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            return {
                "success": True,
                "jobs_found": jobs_added,
                "developers_found": devs_added,
                "analyzed": analyzed_count,
                "stopped": stopped_count > 0,
                "remaining": stopped_count,
                "warning": f"Commit failed: {str(e)[:100]}",
            }

        status = "stopped" if stopped_count > 0 else "completed"
        await update_operation(db, operation_id, status=status)
        await broadcast_progress("analyze_complete", {
            "channel": source_name,
            "channel_id": source_id,
            "analyzed": analyzed_count,
            "jobs": jobs_added,
            "developers": devs_added,
            "operation_id": operation_id,
        })
        logger.info(f"[ANALYZE WEBSITE] ✓ COMPLETE | source={source_name} | analyzed={analyzed_count}/{total_messages} | jobs_saved={jobs_added} | devs_saved={devs_added} | skipped={skipped_count} | status={status} | tokens: in={total_input_tokens} out={total_output_tokens}")

        return {
            "success": True,
            "analyzed": analyzed_count,
            "jobs_found": jobs_added,
            "developers_found": devs_added,
            "skipped": skipped_count,
            "stopped": stopped_count > 0,
            "remaining": stopped_count,
        }

    except Exception as e:
        logger.error(f"[ANALYZE WEBSITE] Error: {e}", exc_info=True)
        await broadcast_progress("error", {
            "channel": source_name,
            "channel_id": source_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}

    finally:
        await cleanup_website_stop_event(source_id)
