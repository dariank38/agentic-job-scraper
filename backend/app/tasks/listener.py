"""Real-time Telegram message listener management."""

import asyncio
import logging
import shutil
from typing import Optional

from sqlalchemy import select

from app.connection import AsyncSessionLocal
from app.models import Channel, Message, TelegramAccount
from app.tasks.operations import broadcast_progress
from app.tasks.stop_events import get_fetch_lock
from telegram_processor import TelegramClientManager
from telegram_processor.config import TELEGRAM_SESSION_PATH
from telegram_processor.listener import TelegramMessageListener
from app.tasks.analyze import _analyze_single
from app.tasks.operations import broadcast_progress as _bp
from services.ollama_service import (get_analyzer, is_ollama_available)

logger = logging.getLogger(__name__)

# Real-time listener state — keyed by telegram_account_id
telegram_listeners: dict[int, TelegramMessageListener] = {}
telegram_listener_running: dict[int, bool] = {}
telegram_listener_tasks: dict[int, asyncio.Task] = {}


def is_listener_running(account_id: int = None) -> bool:
    if account_id is not None:
        return telegram_listener_running.get(account_id, False)
    return any(telegram_listener_running.values())


async def start_telegram_listener(
    channel_usernames: list[str],
    auto_analyze: bool = False,
    telegram_account_id: Optional[int] = None,
) -> dict:
    global telegram_listeners, telegram_listener_running, telegram_listener_tasks

    async with AsyncSessionLocal() as db:
        if telegram_account_id:
            account_result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == telegram_account_id))
            account = account_result.scalar_one_or_none()
            if not account:
                return {"success": False, "error": "Telegram account not found"}
        else:
            account_result = await db.execute(
                select(TelegramAccount).filter(TelegramAccount.is_authenticated == True).limit(1)
            )
            account = account_result.scalar_one_or_none()
            if not account:
                return {"success": False, "error": "No authenticated Telegram account found"}
            telegram_account_id = account.id

    if telegram_listener_running.get(telegram_account_id, False):
        return {"success": False, "error": f"Listener already running for account {account.phone_number}"}

    try:
        async with AsyncSessionLocal() as db:
            for username in channel_usernames:
                clean_username = username.lstrip('@')
                channel_result = await db.execute(select(Channel).filter(Channel.username == f"@{clean_username}"))
                channel = channel_result.scalar_one_or_none()
                if not channel:
                    channel_result = await db.execute(select(Channel).filter(Channel.username == clean_username))
                    channel = channel_result.scalar_one_or_none()
                if channel:
                    channel.is_listened = 1
                    channel.telegram_account_id = telegram_account_id
            await db.commit()

        listener_session_name = f"{account.session_name}_listener"
        original_session = TELEGRAM_SESSION_PATH.parent / f"{account.session_name}.session"
        listener_session = TELEGRAM_SESSION_PATH.parent / f"{listener_session_name}.session"

        fetch_lock = await get_fetch_lock(telegram_account_id)
        async with fetch_lock:
            if original_session.exists() and (not listener_session.exists() or
                    original_session.stat().st_mtime > listener_session.stat().st_mtime):
                shutil.copy2(str(original_session), str(listener_session))
                logger.info(f"Copied session file for listener: {listener_session_name}")

        client_manager = TelegramClientManager(
            api_id=account.api_id,
            api_hash=account.api_hash,
            phone_number=account.phone_number,
            session_name=listener_session_name,
        )
        await client_manager.connect()

        listener = TelegramMessageListener(client_manager)
        telegram_listeners[telegram_account_id] = listener

        _auto_analyze_enabled_ref = [False]

        async def on_new_message(event, message_data):
            try:
                async with AsyncSessionLocal() as db:
                    channel_username_str = (message_data.get('channel_username') or '').lstrip('@')
                    channel_id = message_data.get('channel_id')
                    channel = None

                    if channel_id:
                        channel_result = await db.execute(select(Channel).filter(Channel.telegram_id == channel_id))
                        channel = channel_result.scalar_one_or_none()

                    if not channel and channel_username_str:
                        channel_result = await db.execute(select(Channel).filter(Channel.username == f"@{channel_username_str}"))
                        channel = channel_result.scalar_one_or_none()
                        if not channel:
                            channel_result = await db.execute(select(Channel).filter(Channel.username == channel_username_str))
                            channel = channel_result.scalar_one_or_none()

                    if not channel:
                        identifier = channel_username_str or f"telegram_id:{channel_id}"
                        normalized_username = f"@{channel_username_str}" if channel_username_str and not channel_username_str.startswith('@') else channel_username_str
                        channel = Channel(
                            username=normalized_username or None,
                            telegram_id=channel_id,
                            name=message_data.get('channel_name', identifier),
                            telegram_account_id=telegram_account_id,
                            is_active=1,
                            is_listened=1,
                        )
                        db.add(channel)
                        await db.commit()
                        await db.refresh(channel)

                    existing_result = await db.execute(select(Message).filter(Message.text == message_data['text']))
                    if existing_result.scalars().first():
                        return

                    message_date = message_data['date']
                    if message_date and message_date.tzinfo is not None:
                        message_date = message_date.replace(tzinfo=None)

                    message = Message(
                        channel_id=channel.id,
                        telegram_id=message_data['id'],
                        text=message_data['text'],
                        date=message_date,
                        sender_id=message_data['sender_id'],
                        sender_username=message_data['sender_username'],
                        sender_first_name=message_data['sender_first_name'],
                        has_image=message_data['has_media'],
                        analysis_status="pending",
                    )
                    db.add(message)
                    await db.commit()

                    logger.info(f"Saved new message from {channel_username_str}: {message_data['text'][:50]}...")
                    await broadcast_progress("new_message", {
                        "channel": channel_username_str,
                        "message_id": message.id,
                        "text": message_data['text'][:100],
                        "account_id": telegram_account_id,
                    })

                    

                    if auto_analyze and await is_ollama_available():
                        analyzer = get_analyzer()
                        message, result, error = await _analyze_single(analyzer, message, channel_username_str)
                        if not error:
                            message.analysis_status = "analyzed" if result and result.get("category") != "other" else "skipped"
                            await db.commit()
                        else:
                            logger.error(f"Auto-analyze failed for new message: {error}")
            except Exception as e:
                logger.error(f"Error handling new message: {e}", exc_info=True)

        await listener.start(channel_usernames=channel_usernames, on_new_message=on_new_message)
        telegram_listener_running[telegram_account_id] = True

        async def keep_listener_alive():
            while telegram_listener_running.get(telegram_account_id, False) and listener.is_running:
                await asyncio.sleep(1)
            logger.info(f"Listener stopped for account {account.phone_number}")

        telegram_listener_tasks[telegram_account_id] = asyncio.create_task(keep_listener_alive())

        return {
            "success": True,
            "listening_to": channel_usernames,
            "auto_analyze": auto_analyze,
            "account_id": telegram_account_id,
            "phone_number": account.phone_number,
        }

    except Exception as e:
        logger.error(f"Error starting listener: {e}", exc_info=True)
        telegram_listener_running[telegram_account_id] = False
        return {"success": False, "error": str(e)}


async def stop_telegram_listener(telegram_account_id: Optional[int] = None) -> dict:
    global telegram_listeners, telegram_listener_running, telegram_listener_tasks

    if telegram_account_id is not None:
        if not telegram_listener_running.get(telegram_account_id, False):
            return {"success": False, "error": f"Listener not running for account {telegram_account_id}"}
        try:
            telegram_listener_running[telegram_account_id] = False
            listener = telegram_listeners.pop(telegram_account_id, None)
            if listener:
                await listener.stop()
            task = telegram_listener_tasks.pop(telegram_account_id, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            return {"success": True, "account_id": telegram_account_id}
        except Exception as e:
            logger.error(f"Error stopping listener for account {telegram_account_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    results = []
    for account_id in list(telegram_listener_running.keys()):
        if telegram_listener_running.get(account_id, False):
            results.append(await stop_telegram_listener(account_id))

    if any(r["success"] for r in results):
        return {"success": True, "stopped": len([r for r in results if r["success"]])}
    return {"success": False, "error": "No listeners were running"}


async def add_listener_channels(channel_usernames: list[str], telegram_account_id: Optional[int] = None) -> dict:
    if telegram_account_id is None:
        running_accounts = [aid for aid, running in telegram_listener_running.items() if running]
        if len(running_accounts) == 1:
            telegram_account_id = running_accounts[0]
        elif len(running_accounts) == 0:
            return {"success": False, "error": "Channel must be assigned to a Telegram account. Please edit the channel and assign it to an account."}
        else:
            return {"success": False, "error": "Multiple listeners running - account_id required"}

    if not telegram_listener_running.get(telegram_account_id, False):
        start_result = await start_telegram_listener(channel_usernames, auto_analyze=False, telegram_account_id=telegram_account_id)
        if not start_result.get("success"):
            return {"success": False, "error": start_result.get("error", "Failed to start listener")}
        return start_result

    try:
        listener = telegram_listeners.get(telegram_account_id)
        if listener:
            await listener.add_channels(channel_usernames)

        async with AsyncSessionLocal() as db:
            updated_channels = []
            for username in channel_usernames:
                clean_username = username.lstrip('@')
                channel_result = await db.execute(select(Channel).filter(Channel.username == f"@{clean_username}"))
                channel = channel_result.scalar_one_or_none()
                if not channel:
                    channel_result = await db.execute(select(Channel).filter(Channel.username == clean_username))
                    channel = channel_result.scalar_one_or_none()
                if channel:
                    channel.is_listened = 1
                    channel.telegram_account_id = telegram_account_id
                    updated_channels.append({"id": channel.id, "username": channel.username, "is_listened": 1, "telegram_account_id": telegram_account_id})
            await db.commit()

        if updated_channels:
            await broadcast_progress("channel_update", {"channels": updated_channels})

        return {
            "success": True,
            "listening_to": listener.listened_channels if listener else [],
            "account_id": telegram_account_id,
        }
    except Exception as e:
        logger.error(f"Error adding channels to listener: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def remove_listener_channels(channel_usernames: list[str], telegram_account_id: Optional[int] = None) -> dict:
    if telegram_account_id is None:
        running_accounts = [aid for aid, running in telegram_listener_running.items() if running]
        if len(running_accounts) == 1:
            telegram_account_id = running_accounts[0]
        elif len(running_accounts) == 0:
            return {"success": False, "error": "No listener is running"}
        else:
            return {"success": False, "error": "Multiple listeners running - account_id required"}

    if not telegram_listener_running.get(telegram_account_id, False):
        return {"success": False, "error": f"Listener not running for account {telegram_account_id}"}

    try:
        listener = telegram_listeners.get(telegram_account_id)
        if listener:
            await listener.remove_channels(channel_usernames)

        async with AsyncSessionLocal() as db:
            updated_channels = []
            for username in channel_usernames:
                clean_username = username.lstrip('@')
                channel_result = await db.execute(select(Channel).filter(Channel.username == f"@{clean_username}"))
                channel = channel_result.scalar_one_or_none()
                if not channel:
                    channel_result = await db.execute(select(Channel).filter(Channel.username == clean_username))
                    channel = channel_result.scalar_one_or_none()
                if channel:
                    channel.is_listened = 0
                    updated_channels.append({"id": channel.id, "username": channel.username, "is_listened": 0, "telegram_account_id": channel.telegram_account_id})
            await db.commit()

        if updated_channels:
            await broadcast_progress("channel_update", {"channels": updated_channels})

        return {
            "success": True,
            "listening_to": listener.listened_channels if listener and telegram_listener_running.get(telegram_account_id) else [],
            "account_id": telegram_account_id,
        }
    except Exception as e:
        logger.error(f"Error removing channels from listener: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_listener_channels(telegram_account_id: Optional[int] = None) -> dict:
    try:
        if telegram_account_id is not None:
            listener = telegram_listeners.get(telegram_account_id)
            if listener and telegram_listener_running.get(telegram_account_id, False):
                return {"success": True, "listening_to": listener.listened_channels, "account_id": telegram_account_id}
            return {"success": True, "listening_to": [], "account_id": telegram_account_id}

        all_channels = []
        for account_id, listener in telegram_listeners.items():
            if telegram_listener_running.get(account_id, False):
                all_channels.extend(listener.listened_channels)

        return {"success": True, "listening_to": list(set(all_channels))}
    except Exception as e:
        logger.error(f"Error getting listener channels: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def restore_listeners_from_db():
    try:
        async with AsyncSessionLocal() as db:
            accounts_result = await db.execute(select(TelegramAccount))
            accounts = accounts_result.scalars().all()
            for account in accounts:
                if not account.is_authenticated:
                    try:
                        manager = TelegramClientManager(
                            api_id=account.api_id,
                            api_hash=account.api_hash,
                            phone_number=account.phone_number,
                            session_name=account.session_name,
                        )
                        await manager.connect()
                        account.is_authenticated = True
                        await manager.disconnect()
                    except Exception:
                        pass
            await db.commit()

            channels_result = await db.execute(select(Channel).filter(Channel.is_listened == 1))
            channels = channels_result.scalars().all()
            if not channels:
                return

            channels_by_account: dict[int, list[str]] = {}
            for channel in channels:
                account_id = channel.telegram_account_id
                if account_id is None:
                    continue
                channels_by_account.setdefault(account_id, []).append(channel.username)

            for account_id, usernames in channels_by_account.items():
                try:
                    account_result = await db.execute(select(TelegramAccount).filter(TelegramAccount.id == account_id))
                    account = account_result.scalar_one_or_none()
                    if not account or not account.is_authenticated:
                        continue
                    result = await start_telegram_listener(usernames, telegram_account_id=account_id)
                    if result.get("success"):
                        logger.info(f"Restored listener for account {account.phone_number} with {len(usernames)} channels")
                    else:
                        logger.error(f"Failed to restore listener for account {account_id}: {result.get('error')}")
                except Exception as e:
                    logger.error(f"Error restoring listener for account {account_id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error restoring listeners from database: {e}", exc_info=True)
