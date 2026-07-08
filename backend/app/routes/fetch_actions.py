"""Fetch-related API routes."""

import logging
import uuid
from typing import Optional

from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connection import AsyncSessionLocal, get_db
from app.models import Channel
from app.tasks import (broadcast_progress, cleanup_bulk_stop_event,
                       cleanup_stale_operations, fetch_and_store_messages,
                       is_bulk_operation_stopped, reset_bulk_stop_event)
from telegram_processor.config import DEFAULT_DAYS_BACK

logger = logging.getLogger(__name__)


def register_fetch_action_routes(app):

    async def _fetch_channel_bg(channel_id: int, account_id: Optional[int] = None):
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                channel = result.scalar_one_or_none()
                if channel:
                    channel_name = channel.username or channel.name or f"ID:{channel_id}"
                    logger.info(f"[BG TASK] Fetching from @{channel_name} (ID: {channel_id})")
                    fetch_result = await fetch_and_store_messages(db, channel, days_back=DEFAULT_DAYS_BACK, account_id=account_id)
                    logger.info(f"[BG TASK] Completed fetch for @{channel_name}: {fetch_result.get('new_stored', 0)} new messages")
                else:
                    logger.warning(f"[BG TASK] Channel {channel_id} not found")
            except Exception as e:
                logger.error(f"[BG TASK] Exception during fetch for channel {channel_id}: {e}", exc_info=True)

    @app.post("/api/fetch/{channel_id}")
    async def fetch_channel(channel_id: int, account_id: Optional[int] = None, background_tasks: BackgroundTasks = None, db: AsyncSession = Depends(get_db)):
        try:
            result = await db.execute(select(Channel).filter(Channel.id == channel_id))
            channel = result.scalar_one_or_none()
            if not channel:
                raise HTTPException(status_code=404, detail="Channel not found")
            background_tasks.add_task(_fetch_channel_bg, channel_id, account_id)
            return {"success": True, "message": f"Fetch started for @{channel.username}", "channel": channel.username}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start fetch: {str(e)}")

    async def _run_fetch_all(channel_ids: list, operation_id: str):
        logger.info(f"[BULK FETCH] Starting operation {operation_id} for {len(channel_ids)} channels")
        await reset_bulk_stop_event(operation_id)
        success_count = error_count = total_new_messages = 0

        await broadcast_progress("bulk_fetch_start", {"operation_id": operation_id, "total_channels": len(channel_ids)})
        try:
            for idx, channel_id in enumerate(channel_ids):
                if is_bulk_operation_stopped(operation_id):
                    logger.info(f"[BULK FETCH] Operation {operation_id} stopped at channel {idx+1}/{len(channel_ids)}")
                    await broadcast_progress("bulk_fetch_stopped", {"operation_id": operation_id, "progress": idx, "total": len(channel_ids)})
                    break
                async with AsyncSessionLocal() as db:
                    try:
                        result = await db.execute(select(Channel).filter(Channel.id == channel_id))
                        channel = result.scalar_one_or_none()
                        if channel:
                            fetch_result = await fetch_and_store_messages(db, channel, days_back=DEFAULT_DAYS_BACK)
                            new_messages = fetch_result.get("new_stored", 0)
                            total_new_messages += new_messages
                            success_count += 1
                            await broadcast_progress("bulk_fetch_progress", {
                                "operation_id": operation_id,
                                "progress": idx + 1,
                                "total": len(channel_ids),
                                "channel": channel.username,
                                "new_messages": new_messages,
                            })
                        else:
                            logger.warning(f"[BULK FETCH] Channel {channel_id} not found")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"[BULK FETCH] Exception in channel {channel_id}: {e}", exc_info=True)

            await broadcast_progress("bulk_fetch_complete", {
                "operation_id": operation_id,
                "success_count": success_count,
                "error_count": error_count,
                "total_new_messages": total_new_messages,
            })
        finally:
            cleanup_bulk_stop_event(operation_id)

    @app.post("/api/fetch-all")
    async def fetch_all(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
        try:
            await cleanup_stale_operations()
            result = await db.execute(select(Channel).filter(Channel.is_active == True))
            channels = result.scalars().all()
            if not channels:
                return {"success": False, "message": "No active channels found"}
            operation_id = f"fetch-all-{uuid.uuid4().hex[:8]}"
            await reset_bulk_stop_event(operation_id)
            background_tasks.add_task(_run_fetch_all, [c.id for c in channels], operation_id)
            return {"success": True, "message": f"Fetch started for {len(channels)} channel(s)", "operation_id": operation_id, "channels": len(channels)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start fetch all: {str(e)}")

    @app.get("/api/telegram-dialogs")
    async def get_telegram_dialogs(account_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
        try:
            from app.models import TelegramAccount
            from app.tasks import get_fetch_lock
            from telegram_processor import TelegramClientManager, get_dialogs

            if account_id:
                result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
                account = result.scalar_one_or_none()
                if not account:
                    raise HTTPException(status_code=404, detail="Telegram account not found")
            else:
                result = await db.execute(
                    select(TelegramAccount).filter(TelegramAccount.is_active == True, TelegramAccount.is_authenticated == True)
                )
                account = result.scalars().first()
                if not account:
                    raise HTTPException(status_code=400, detail="No active authenticated Telegram account found. Please add a Telegram account in Settings > Telegram Accounts and authenticate it first.")

            result = await db.execute(select(Channel.username))
            existing_usernames = set(row[0].lower() for row in result.all() if row[0])

            telegram_manager = TelegramClientManager(
                api_id=account.api_id,
                api_hash=account.api_hash,
                phone_number=account.phone_number,
                session_name=account.session_name,
            )
            fetch_lock = await get_fetch_lock(account.id)
            async with fetch_lock:
                await telegram_manager.connect()
                try:
                    dialogs = await get_dialogs(telegram_manager.client)
                finally:
                    await telegram_manager.disconnect()

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
