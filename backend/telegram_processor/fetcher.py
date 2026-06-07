"""Telegram message fetcher with FloodWait handling."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from telethon.errors import FloodWaitError
from telethon import TelegramClient
from telethon.tl.types import User, Channel, MessageMediaPhoto

from telegram_processor.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_DELAY,
)


async def _get_sender_info(
    client: TelegramClient,
    sender_id: int,
    sender_cache: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Get sender username/info with caching."""
    if sender_id in sender_cache:
        return sender_cache[sender_id]

    info = {
        "id": sender_id,
        "username": None,
        "first_name": None,
        "last_name": None,
        "type": "unknown",
    }

    try:
        entity = await client.get_entity(sender_id)

        if isinstance(entity, User):
            info["type"] = "user"
            info["username"] = entity.username
            info["first_name"] = entity.first_name
            info["last_name"] = entity.last_name
        elif isinstance(entity, Channel):
            info["type"] = "channel"
            info["username"] = entity.username
            info["first_name"] = entity.title
    except Exception:
        pass

    sender_cache[sender_id] = info
    return info


async def fetch_messages(
    client: TelegramClient,
    channel_username: str,
    days_back: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
    _offset_id: int | None = None,  # Internal: resume point for FloodWait retry
) -> list[dict[str, Any]]:
    """Fetch messages from today (since midnight UTC) with batch processing.

    Args:
        client: Connected TelegramClient instance.
        channel_username: The channel username (e.g., @jobschannel).
        days_back: Extra days before today to include (0 = today only).
        batch_size: Messages per API call (default: 50).
        batch_delay: Seconds to wait between batches (default: 1.0).
        _offset_id: Internal resume parameter used by FloodWait retry.

    Returns:
        List of all message dictionaries from today.
    """
    messages: list[dict[str, Any]] = []

    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today_midnight - timedelta(days=days_back)

    last_id: int | None = _offset_id
    reached_cutoff = False

    sender_cache: dict[int, dict[str, Any]] = {}

    try:
        while not reached_cutoff:
            batch: list[dict[str, Any]] = []
            batch_count = 0

            async for message in client.iter_messages(
                channel_username,
                limit=batch_size,
                offset_id=last_id - 1 if last_id else 0,
            ):
                if not message or not message.text:
                    continue

                if message.date and message.date < cutoff_date:
                    reached_cutoff = True
                    break

                sender_info = None
                if message.sender_id:
                    sender_info = await _get_sender_info(
                        client, message.sender_id, sender_cache
                    )

                has_image = False
                if message.media and isinstance(message.media, MessageMediaPhoto):
                    has_image = True

                msg_date = message.date
                if msg_date and msg_date.tzinfo is not None:
                    msg_date = msg_date.replace(tzinfo=None)

                batch.append({
                    "id": message.id,
                    "date": msg_date,
                    "text": message.text,
                    "sender_id": message.sender_id,
                    "sender": sender_info,
                    "has_image": has_image,
                })
                batch_count += 1
                last_id = message.id

            if batch:
                messages.extend(batch)

            if batch_count < batch_size or reached_cutoff:
                break

            if not reached_cutoff:
                await asyncio.sleep(batch_delay)

    except FloodWaitError as e:
        wait_time = e.seconds
        print(f"FloodWaitError: waiting {wait_time} seconds before resuming from id={last_id}...")
        await asyncio.sleep(wait_time)
        return messages + await fetch_messages(
            client, channel_username, days_back, batch_size, batch_delay,
            _offset_id=last_id,
        )

    return messages


async def get_dialogs(client: TelegramClient) -> list[dict[str, Any]]:
    """Get available Telegram dialogs (channels/groups).

    Args:
        client: Connected TelegramClient instance.

    Returns:
        List of dialog dictionaries with channel/group information.
    """
    dialogs = []

    async for dialog in client.iter_dialogs():
        if dialog.is_channel or dialog.is_group:
            entity = dialog.entity
            # Use dialog.name which works for both channels and groups
            name = dialog.name or getattr(entity, "title", None) or str(entity.id)
            dialogs.append({
                "id": entity.id,
                "username": getattr(entity, "username", None),
                "name": name,
                "type": "channel" if dialog.is_channel else "group",
            })

    return dialogs