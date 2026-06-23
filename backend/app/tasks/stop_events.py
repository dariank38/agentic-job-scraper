"""Stop events and fetch locks for per-channel/source/bulk operations."""

import asyncio
import os

MAX_CONSECUTIVE_FAILURES = int(os.getenv("MAX_CONSECUTIVE_FAILURES", "20"))

# Global stop events for cancelling analysis (per-channel)
analysis_stop_events: dict[int, asyncio.Event] = {}
analysis_stop_events_lock = asyncio.Lock()

# Per-account fetch locks to prevent SQLite session conflicts
fetch_locks: dict[int, asyncio.Lock] = {}
fetch_locks_lock = asyncio.Lock()

# Website source stop events
website_stop_events: dict[int, asyncio.Event] = {}
website_stop_events_lock = asyncio.Lock()

# Bulk operation stop events
bulk_stop_events: dict[str, asyncio.Event] = {}
bulk_stop_events_lock = asyncio.Lock()


async def get_fetch_lock(account_id: int) -> asyncio.Lock:
    async with fetch_locks_lock:
        if account_id not in fetch_locks:
            fetch_locks[account_id] = asyncio.Lock()
        return fetch_locks[account_id]


async def reset_stop_event(channel_id: int):
    async with analysis_stop_events_lock:
        stale = [cid for cid, e in list(analysis_stop_events.items()) if e.is_set()]
        for cid in stale:
            analysis_stop_events.pop(cid, None)
        analysis_stop_events[channel_id] = asyncio.Event()


async def stop_analysis(channel_id: int):
    async with analysis_stop_events_lock:
        if channel_id in analysis_stop_events:
            analysis_stop_events[channel_id].set()


def is_analysis_stopped(channel_id: int) -> bool:
    event = analysis_stop_events.get(channel_id)
    return event.is_set() if event else False


async def cleanup_stop_event(channel_id: int):
    async with analysis_stop_events_lock:
        analysis_stop_events.pop(channel_id, None)


async def reset_website_stop_event(source_id: int):
    async with website_stop_events_lock:
        website_stop_events[source_id] = asyncio.Event()


async def stop_website_operation(source_id: int):
    async with website_stop_events_lock:
        if source_id in website_stop_events:
            website_stop_events[source_id].set()


def is_website_operation_stopped(source_id: int) -> bool:
    event = website_stop_events.get(source_id)
    return event.is_set() if event else False


async def cleanup_website_stop_event(source_id: int):
    async with website_stop_events_lock:
        website_stop_events.pop(source_id, None)


async def reset_bulk_stop_event(operation_id: str):
    async with bulk_stop_events_lock:
        bulk_stop_events[operation_id] = asyncio.Event()


async def stop_bulk_operation(operation_id: str):
    async with bulk_stop_events_lock:
        if operation_id in bulk_stop_events:
            bulk_stop_events[operation_id].set()


def is_bulk_operation_stopped(operation_id: str) -> bool:
    event = bulk_stop_events.get(operation_id)
    return event.is_set() if event else False


def cleanup_bulk_stop_event(operation_id: str):
    bulk_stop_events.pop(operation_id, None)


async def cleanup_old_stop_events(max_age_seconds: int = 3600):
    async with analysis_stop_events_lock:
        stale = [cid for cid, e in list(analysis_stop_events.items()) if e.is_set()]
        for cid in stale:
            analysis_stop_events.pop(cid, None)
    async with bulk_stop_events_lock:
        stale_bulk = [oid for oid, e in list(bulk_stop_events.items()) if e.is_set()]
        for oid in stale_bulk:
            bulk_stop_events.pop(oid, None)
