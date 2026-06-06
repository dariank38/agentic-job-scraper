"""Database connection and session management."""

import os
from typing import Set
from fastapi import WebSocket

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from telegram_processor.config import DATABASE_URL

# Validate DATABASE_URL
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required. Please set it in your .env file.")

# Async engine with connection pooling for PostgreSQL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class ConnectionManager:
    """WebSocket connection manager for real-time progress updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        import json
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.discard(connection)


manager = ConnectionManager()


async def init_db() -> None:
    """Initialize database tables."""
    from app import models

    try:
        async with engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


async def get_db() -> AsyncSession:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        yield session
