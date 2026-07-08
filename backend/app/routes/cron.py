"""Cron job and auto-analyze API routes."""

import logging

from fastapi import HTTPException, Query

from app.tasks import (broadcast_progress, get_auto_analyze, is_cron_running,
                       set_auto_analyze, start_cron_task, stop_cron_task)

logger = logging.getLogger(__name__)


def register_cron_routes(app):

    @app.post("/api/cron/start")
    async def start_cron():
        try:
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
        try:
            stopped = await stop_cron_task()
            if stopped:
                await broadcast_progress("cron_status", {"running": False})
                return {"success": True, "message": "Cron job stopped"}
            else:
                return {"success": False, "message": "Cron job is not running"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop cron: {str(e)}")

    @app.get("/api/cron/status")
    async def cron_status():
        try:
            return {"success": True, "running": is_cron_running()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get cron status: {str(e)}")

    @app.get("/api/auto-analyze")
    async def get_auto_analyze_status():
        return {"success": True, "enabled": get_auto_analyze()}

    @app.post("/api/auto-analyze")
    async def set_auto_analyze_status(enabled: bool = Query(..., description="Enable or disable auto-analyze")):
        set_auto_analyze(enabled)
        return {"success": True, "enabled": enabled}
