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
    """Get sender username/info with caching.

    Args:
        client: TelegramClient instance.
        sender_id: The sender ID from message.
        sender_cache: Cache dict for sender info.

    Returns:
        Dict with username, first_name, last_name, type.
    """
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
        # Negative IDs are channels/groups, positive are users
        entity = await client.get_entity(sender_id)

        if isinstance(entity, User):
            info["type"] = "user"
            info["username"] = entity.username
            info["first_name"] = entity.first_name
            info["last_name"] = entity.last_name
        elif isinstance(entity, Channel):
            info["type"] = "channel"
            info["username"] = entity.username
            info["first_name"] = entity.title  # Channels have title instead
    except Exception:
        # Entity not found or no access - keep defaults
        pass

    sender_cache[sender_id] = info
    return info


async def fetch_messages(
    client: TelegramClient,
    channel_username: str,
    days_back: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
) -> list[dict[str, Any]]:
    """Fetch messages from today (since midnight UTC) with batch processing.

    Designed for cron job operation - fetches in small batches with
    delays to avoid rate limits.

    Args:
        client: Connected TelegramClient instance.
        channel_username: The channel username (e.g., @jobschannel).
        days_back: Extra days before today to include (0 = today only).
        batch_size: Messages per API call (default: 50).
        batch_delay: Seconds to wait between batches (default: 1.0).

    Returns:
        List of all message dictionaries from today.
    """
    messages: list[dict[str, Any]] = []

    # Cutoff = start of today UTC (midnight) minus any extra days_back
    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today_midnight - timedelta(days=days_back)

    # Track the last message ID for pagination
    last_id: int | None = None
    reached_cutoff = False

    # Cache for sender info to avoid duplicate API calls
    sender_cache: dict[int, dict[str, Any]] = {}

    try:
        while not reached_cutoff:
            batch: list[dict[str, Any]] = []
            batch_count = 0

            # Fetch one batch
            async for message in client.iter_messages(
                channel_username,
                limit=batch_size,
                offset_id=last_id - 1 if last_id else 0,
            ):
                if not message or not message.text:
                    continue

                # Check if we've reached the cutoff date
                if message.date and message.date < cutoff_date:
                    reached_cutoff = True
                    break

                # Get sender info (with caching)
                sender_info = None
                if message.sender_id:
                    sender_info = await _get_sender_info(
                        client, message.sender_id, sender_cache
                    )

                # Check if message contains an image
                has_image = False
                if message.media and isinstance(message.media, MessageMediaPhoto):
                    has_image = True

                # Normalize date to naive UTC datetime for SQLite compatibility
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

            # No more messages or reached cutoff
            if batch_count < batch_size or reached_cutoff:
                break

            # Delay before next batch (cron-friendly rate limiting)
            if not reached_cutoff:
                await asyncio.sleep(batch_delay)

    except FloodWaitError as e:
        wait_time = e.seconds
        print(f"FloodWaitError: waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        # Retry from where we left off
        return messages + await fetch_messages(
            client, channel_username, days_back, batch_size, batch_delay
        )

    return messages
