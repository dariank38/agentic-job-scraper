"""Fetch messages from Telegram and store in database."""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisRun, Channel, Message, TelegramAccount
from telegram_processor import TelegramClientManager, fetch_messages
from app.tasks.stop_events import get_fetch_lock, is_bulk_operation_stopped
from app.tasks.operations import (
    broadcast_progress,
    broadcast_stats_update,
    create_operation,
    update_operation,
)

logger = logging.getLogger(__name__)


async def fetch_and_store_messages(
    db: AsyncSession,
    channel: Channel,
    days_back: int = 2,
    run_id: Optional[int] = None,
    account_id: Optional[int] = None,
    bulk_operation_id: Optional[str] = None,
) -> dict:
    channel_id = channel.id
    channel_username = channel.username or channel.name or f"ID:{channel.id}"

    if account_id:
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
        account = result.scalar_one_or_none()
        if not account:
            return {"success": False, "error": "Telegram account not found"}
    elif channel.telegram_account_id:
        result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == channel.telegram_account_id))
        account = result.scalar_one_or_none()
        if not account:
            return {"success": False, "error": "Associated Telegram account not found"}
    else:
        result = await db.execute(
            select(TelegramAccount).filter(
                TelegramAccount.is_active == True,
                TelegramAccount.is_authenticated == True,
            )
        )
        account = result.scalars().first()
        if not account:
            return {
                "success": False,
                "error": "No active authenticated Telegram account found. Please add and authenticate an account in settings.",
            }

    telegram_manager = TelegramClientManager(
        api_id=account.api_id,
        api_hash=account.api_hash,
        phone_number=account.phone_number,
        session_name=account.session_name,
    )

    fetch_lock = await get_fetch_lock(account.id)
    operation_id = await create_operation(db, "fetch", channel, bulk_operation_id=bulk_operation_id)

    try:
        async with fetch_lock:
            await broadcast_progress("fetch_start", {"channel": channel.username, "days_back": days_back, "operation_id": operation_id})
            await telegram_manager.connect()

            await broadcast_progress("fetch_progress", {"channel": channel.username, "status": "fetching", "operation_id": operation_id})
            messages = await fetch_messages(telegram_manager.client, channel.username, days_back=days_back)
            await broadcast_progress("fetch_progress", {"channel": channel.username, "status": "fetched", "count": len(messages), "operation_id": operation_id})

            await update_operation(db, operation_id, total_messages=len(messages))

            new_count = 0
            stopped_early = False
            for i, msg_data in enumerate(messages):
                if bulk_operation_id and (i % 10 == 0) and is_bulk_operation_stopped(bulk_operation_id):
                    await broadcast_progress("fetch_progress", {
                        "channel": channel.username,
                        "status": "stopped",
                        "processed": i,
                        "total": len(messages),
                        "operation_id": operation_id,
                    })
                    stopped_early = True
                    break

                try:
                    result = await db.execute(select(Message).filter(Message.text == msg_data.get("text")))
                    if result.scalars().first():
                        continue

                    sender = msg_data.get("sender") or {}
                    has_text = bool(msg_data.get("text"))

                    async with db.begin_nested():
                        message = Message(
                            telegram_id=msg_data["id"],
                            channel_id=channel.id,
                            date=msg_data.get("date"),
                            text=msg_data.get("text"),
                            sender_id=msg_data.get("sender_id"),
                            sender_username=sender.get("username"),
                            sender_first_name=sender.get("first_name"),
                            has_image=msg_data.get("has_image", False),
                            analysis_status="pending" if has_text else "skipped",
                        )
                        db.add(message)
                        await db.flush()
                    new_count += 1

                    if (i + 1) % 10 == 0:
                        await broadcast_progress("fetch_progress", {
                            "channel": channel.username,
                            "processed": i + 1,
                            "total": len(messages),
                            "total_messages": len(messages),
                            "analyzed": i + 1,
                            "new": new_count,
                            "operation_id": operation_id,
                        })
                        await update_operation(db, operation_id, current=i + 1, total=len(messages), analyzed=i + 1)
                except Exception:
                    continue

            await db.commit()
            await update_operation(db, operation_id, status="completed")
            await broadcast_progress("fetch_complete", {
                "channel": channel.username,
                "new_messages": new_count,
                "operation_id": operation_id,
            })
            logger.info(f"[FETCH] Completed for {channel_username}: {new_count} new messages")

            channel.last_fetch_new_count = new_count
            channel.last_fetch_at = datetime.utcnow()
            await db.commit()

            await broadcast_stats_update(db)

            if run_id:
                try:
                    result = await db.execute(select(AnalysisRun).filter(AnalysisRun.id == run_id))
                    run = result.scalar_one_or_none()
                    if run:
                        run.messages_fetched += len(messages)
                        await db.commit()
                except Exception:
                    await db.rollback()

            return {"success": True, "fetched": len(messages), "new_stored": new_count}

    except Exception as e:
        await db.rollback()
        await update_operation(db, operation_id, status="error", error_message=str(e))

        await broadcast_progress("error", {
            "channel": channel_username,
            "channel_id": channel_id,
            "operation_id": operation_id,
            "error": str(e),
        })
        error_msg = str(e).lower()
        invalid_channel_errors = [
            "channel not found", "channel invalid", "username not occupied",
            "username invalid", "no such entity", "private", "forbidden",
        ]
        if any(err in error_msg for err in invalid_channel_errors):
            try:
                await db.delete(channel)
                await db.commit()
            except Exception:
                await db.rollback()
            return {"success": False, "error": f"Channel removed: {str(e)}", "channel_removed": True}

        return {"success": False, "error": str(e)}

    finally:
        try:
            await telegram_manager.disconnect()
        except Exception:
            pass
