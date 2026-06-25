"""Database connection and session management."""

import logging
import os
from typing import Set
from fastapi import WebSocket

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from telegram_processor.config import DATABASE_URL

logger = logging.getLogger(__name__)

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
        """Accept a new WebSocket connection."""
        try:
            await websocket.accept()
            self.active_connections.add(websocket)
            logger.info(f"[WS] Client connected. Total: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"[WS] Error accepting connection: {e}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        import json
        dead_connections = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                # Mark dead connections for removal
                dead_connections.add(connection)
                logger.debug(f"[WS] Failed to send to client: {e}")
        
        # Clean up dead connections
        for dead in dead_connections:
            self.active_connections.discard(dead)
        
        if dead_connections:
            logger.info(f"[WS] Removed {len(dead_connections)} dead connections. Total: {len(self.active_connections)}")


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


async def run_migrations() -> None:
    """Run lightweight schema migrations for additive changes.

    PostgreSQL-specific: add columns that may be missing in existing databases.
    """
    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_manual_skip BOOLEAN DEFAULT FALSE"))
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        raise


async def get_db() -> AsyncSession:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        yield session
