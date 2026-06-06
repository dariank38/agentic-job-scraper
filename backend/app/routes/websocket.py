"""WebSocket-related API routes."""

from fastapi import WebSocket, WebSocketDisconnect

from app.connection import manager


def register_websocket_routes(app):
    """Register websocket-related routes."""

    @app.websocket("/ws/progress")
    async def websocket_progress(websocket: WebSocket):
        """WebSocket endpoint for real-time progress updates."""
        await manager.connect(websocket)
        try:
            while True:
                # Keep connection alive, client can send ping if needed
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)
