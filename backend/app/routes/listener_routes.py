"""Real-time Telegram listener API routes."""

import logging
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.connection import AsyncSessionLocal
from app.models import Channel
from app.tasks import (
    broadcast_progress,
    set_auto_analyze,
    start_telegram_listener,
    stop_telegram_listener,
    add_listener_channels,
    remove_listener_channels,
    get_listener_channels,
    telegram_listener_running,
    telegram_listeners,
)

logger = logging.getLogger(__name__)


def register_listener_routes(app):

    class StartListenerRequest(BaseModel):
        channel_usernames: list[str]
        auto_analyze: bool = False
        telegram_account_id: Optional[int] = None

    @app.post("/api/listener/start")
    async def start_listener(request: StartListenerRequest):
        try:
            set_auto_analyze(request.auto_analyze)
            result = await start_telegram_listener(
                channel_usernames=request.channel_usernames,
                auto_analyze=request.auto_analyze,
                telegram_account_id=request.telegram_account_id,
            )
            if result.get("success"):
                await broadcast_progress("listener_status", {"running": True, "account_id": result.get("account_id")})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start listener: {str(e)}")

    @app.post("/api/listener/stop")
    async def stop_listener(telegram_account_id: Optional[int] = None):
        try:
            result = await stop_telegram_listener(telegram_account_id)
            if result.get("success"):
                await broadcast_progress("listener_status", {"running": False, "account_id": telegram_account_id})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop listener: {str(e)}")

    @app.get("/api/listener/status")
    async def listener_status(telegram_account_id: Optional[int] = None):
        if telegram_account_id is not None:
            running = telegram_listener_running.get(telegram_account_id, False)
            # In-memory channels take priority when listener is active
            listener = telegram_listeners.get(telegram_account_id)
            if running and listener:
                listening_to = listener.listened_channels
            else:
                # Always fall back to DB so channel toggles show correctly even when listener is off
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Channel).filter(Channel.is_listened == 1, Channel.telegram_account_id == telegram_account_id)
                    )
                    db_channels = result.scalars().all()
                    listening_to = [c.username for c in db_channels if c.username]
            return {"running": running, "account_id": telegram_account_id, "listening_to": listening_to}

        # No account_id: aggregate all accounts
        # Collect in-memory running listeners
        active: dict[int, list[str]] = {}
        for aid, running in telegram_listener_running.items():
            if running:
                listener = telegram_listeners.get(aid)
                active[aid] = listener.listened_channels if listener else []

        # Always merge DB is_listened channels so configured-but-stopped accounts appear
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Channel).filter(Channel.is_listened == 1))
            db_channels = result.scalars().all()

        by_account: dict[int, list[str]] = {}
        for ch in db_channels:
            aid = ch.telegram_account_id
            if aid not in by_account:
                by_account[aid] = []
            if ch.username:
                by_account[aid].append(ch.username)

        accounts = []
        all_aids = set(active.keys()) | set(by_account.keys())
        for aid in all_aids:
            running = aid in active
            listening_to = active[aid] if running else by_account.get(aid, [])
            accounts.append({"account_id": aid, "running": running, "listening_to": listening_to})

        return {
            "running": any(a["running"] for a in accounts),
            "accounts": accounts,
            "total_listeners": len(accounts),
        }

    class AddChannelsRequest(BaseModel):
        channel_usernames: list[str]
        telegram_account_id: Optional[int] = None

    @app.post("/api/listener/add-channels")
    async def add_channels(request: AddChannelsRequest):
        try:
            result = await add_listener_channels(request.channel_usernames, request.telegram_account_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add channels: {str(e)}")

    class RemoveChannelsRequest(BaseModel):
        channel_usernames: list[str]
        telegram_account_id: Optional[int] = None

    @app.post("/api/listener/remove-channels")
    async def remove_channels(request: RemoveChannelsRequest):
        try:
            result = await remove_listener_channels(request.channel_usernames, request.telegram_account_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove channels: {str(e)}")

    @app.get("/api/listener/channels")
    async def listener_channels(telegram_account_id: Optional[int] = None):
        try:
            result = await get_listener_channels(telegram_account_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get listener channels: {str(e)}")
