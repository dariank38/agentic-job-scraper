"""Database connection and session management."""

import logging
import os
from typing import Set

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

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
            # Jobs table
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS message_id INTEGER"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_id INTEGER"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS website_source_id INTEGER"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_name VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_type VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS title VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS company VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS company_link VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS location VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_remote BOOLEAN"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS role_type VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS skills JSON"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary VARCHAR(120)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_level VARCHAR(20)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS category VARCHAR(40)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS priority VARCHAR(4)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jd TEXT"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS hr_contact VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS hr_contact_type VARCHAR(255) DEFAULT 'telegram'"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_contact VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS channel_contact_type VARCHAR(255) DEFAULT 'telegram'"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS published_to_jobees BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS published_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS jobees_job_id VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_applied BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_reviewed BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_approved BOOLEAN"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS notes TEXT"))
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMP"))

            # Messages table
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS telegram_id BIGINT"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS website_post_id VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS website_source_id INTEGER"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS source_type VARCHAR(255) DEFAULT 'telegram'"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS date TIMESTAMP"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS text TEXT"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS analysis_text TEXT"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_id BIGINT"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_username VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_first_name VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS has_image BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS needs_reanalysis BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(255) DEFAULT 'pending'"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS skip_reason VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_manual_skip BOOLEAN DEFAULT FALSE"))

            # Developers table
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS message_id INTEGER"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS channel_id INTEGER"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS website_source_id INTEGER"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS name VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS skills JSON"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS experience TEXT"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS portfolio VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS github VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS linkedin VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS contact VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS contact_type VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS looking_for_work BOOLEAN"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS summary TEXT"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS is_contacted BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS contacted_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS notes TEXT"))
            await conn.execute(text("ALTER TABLE developers ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMP"))

            # Channels table
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS telegram_id BIGINT"))
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS telegram_account_id INTEGER"))
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS is_listened INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS last_fetch_new_count INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS last_fetch_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE channels ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"))

            # Website sources table
            await conn.execute(text("ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            await conn.execute(text("ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS last_fetch_new_count INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS last_fetch_at TIMESTAMP"))
            await conn.execute(text("ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS extraction_prompt TEXT"))
            await conn.execute(text("ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS cookies TEXT"))
            await conn.execute(text("ALTER TABLE website_sources ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"))

            # Operations table
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS channel_username VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS bulk_operation_id VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS total_messages INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS analyzed INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS jobs_found INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS developers_found INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS error_message TEXT"))
            await conn.execute(text("ALTER TABLE operations ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP"))

            # Telegram accounts table
            await conn.execute(text("ALTER TABLE telegram_accounts ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            await conn.execute(text("ALTER TABLE telegram_accounts ADD COLUMN IF NOT EXISTS is_authenticated BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE telegram_accounts ADD COLUMN IF NOT EXISTS phone_code_hash VARCHAR(255)"))
            await conn.execute(text("ALTER TABLE telegram_accounts ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP"))

            # Analysis runs table
            await conn.execute(text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS messages_fetched INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS messages_analyzed INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS jobs_found INTEGER DEFAULT 0"))
            await conn.execute(text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS error_message TEXT"))
            await conn.execute(text("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP"))

            # Migrate data from old columns to new ones, then drop old columns
            # Guard with column-existence checks since columns may already be dropped
            await conn.execute(text("""
                DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='summary') THEN
                        UPDATE jobs SET jd = summary WHERE jd IS NULL AND summary IS NOT NULL;
                    END IF;
                END $$;
            """))
            await conn.execute(text("""
                DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='contact') THEN
                        UPDATE jobs SET hr_contact = contact WHERE hr_contact IS NULL AND contact IS NOT NULL;
                    END IF;
                END $$;
            """))
            await conn.execute(text("ALTER TABLE jobs DROP COLUMN IF EXISTS contact"))
            await conn.execute(text("ALTER TABLE jobs DROP COLUMN IF EXISTS contact_type"))
            await conn.execute(text("ALTER TABLE jobs DROP COLUMN IF EXISTS summary"))
            await conn.execute(text("ALTER TABLE jobs DROP COLUMN IF EXISTS confidence"))
            await conn.execute(text("ALTER TABLE developers DROP COLUMN IF EXISTS confidence"))
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        raise


async def get_db() -> AsyncSession:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        yield session
