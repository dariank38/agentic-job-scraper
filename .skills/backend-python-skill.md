---
description: Backend development guidelines for the agentic-job-scraper project using Python, FastAPI, SQLAlchemy, and Telethon
---

# Backend Python Skill

This skill provides guidelines for backend development in the agentic-job-scraper project.

## Tech Stack

- **Language**: Python 3.13
- **Web Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy (async)
- **ORM**: SQLAlchemy with asyncpg driver
- **Telegram Client**: Telethon
- **AI Analysis**: Ollama
- **Async Runtime**: asyncio

## Project Structure

```
backend/
├── app/
│   ├── models.py          # SQLAlchemy models
│   ├── connection.py      # Database connection and session management
│   ├── tasks.py           # Background tasks (fetch, analyze, cron)
│   ├── routes/            # API route handlers
│   │   ├── actions.py     # Action endpoints (fetch, analyze, stop)
│   │   ├── channels.py    # Channel CRUD
│   │   ├── jobs.py        # Job CRUD
│   │   ├── messages.py    # Message CRUD
│   │   ├── operations.py  # Operation status tracking
│   │   ├── stats.py       # Statistics endpoints
│   │   └── telegram_accounts.py
│   └── api_routes.py      # Route registration
├── services/
│   └── ollama_service.py  # Ollama AI analysis service
├── telegram_processor/
│   ├── client.py          # Telegram client manager
│   ├── fetcher.py         # Message fetching logic
│   └── config.py          # Configuration
├── migrations/             # SQL migration files
└── web_app.py             # FastAPI application entry point
```

## Key Patterns

### Database Operations

**Always use async sessions:**
```python
from app.connection import get_db
from sqlalchemy.ext.asyncio import AsyncSession

@app.get("/api/endpoint")
async def endpoint(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).filter(Model.id == id))
    item = result.scalar_one_or_none()
    # ... process item
    await db.commit()
```

**Never use blocking database operations in async context.** All DB operations must be async.

### Telegram Client Usage

**Check authentication before connecting:**
```python
from telegram_processor import TelegramClientManager

telegram_manager = TelegramClientManager(
    api_id=account.api_id,
    api_hash=account.api_hash,
    phone_number=account.phone_number,
    session_name=account.session_name,
)

await telegram_manager.connect(auto_start=True)  # auto_start=True requires authenticated session
# Use telegram_manager.client for operations
await telegram_manager.disconnect()
```

**Important**: The `auto_start=True` parameter requires the session to already be authenticated. If not authenticated, it will raise a RuntimeError. For first-time authentication, use `auto_start=False`.

### Error Handling

**Use HTTPException for API errors:**
```python
from fastapi import HTTPException

if not item:
    raise HTTPException(status_code=404, detail="Item not found")
```

**Add detailed error logging for debugging:**
```python
except Exception as e:
    import traceback
    error_detail = f"{str(e)}\n{traceback.format_exc()}"
    raise HTTPException(status_code=500, detail=f"Operation failed: {error_detail}")
```

### Async Context with Telethon

**Do NOT use asyncio.to_thread for Telethon operations.** Telethon's async operations should run in the main event loop. The blocking `client.start()` is only called during first-time authentication, which we check for with `is_user_authorized()`.

**Correct pattern:**
```python
await telegram_manager.connect()
try:
    dialogs = await get_dialogs(telegram_manager.client)
finally:
    await telegram_manager.disconnect()
```

**Incorrect pattern (causes event loop conflicts):**
```python
# DON'T DO THIS
await asyncio.to_thread(some_telethon_operation)
```

### Operation Tracking

**Create operations for long-running tasks:**
```python
from app.tasks import create_operation, update_operation

operation_id = await create_operation(db, "fetch", channel)
# ... do work
await update_operation(db, operation_id, status="completed")
```

**Broadcast progress via WebSocket:**
```python
from app.tasks import broadcast_progress

await broadcast_progress("fetch_start", {"channel": channel.username, "operation_id": operation_id})
await broadcast_progress("fetch_progress", {"channel": channel.username, "current": 10, "total": 100})
await broadcast_progress("fetch_complete", {"channel": channel.username, "new_messages": 50})
```

## Database Migrations

**Migrations are SQL files in `backend/migrations/`:**
- Check `backend/app/models.py` for current model definitions
- Compare with existing migration files
- Create new SQL migration files for missing changes
- Run migrations manually against PostgreSQL

**Example migration:**
```sql
-- Migration: Add new_column to table
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS new_column VARCHAR(255);
```

## Common Issues

### Event Loop Conflicts

**Symptom**: "greenlet_spawn has not been called" or "event loop must not change after connection"

**Cause**: Using `asyncio.to_thread` with Telethon or creating new event loops in thread pools

**Solution**: Run all Telethon operations in the main event loop. The `client.start()` blocking issue is handled by checking `is_user_authorized()` first.

### Connection Pool Errors

**Symptom**: "got Future attached to a different loop" or connection termination errors

**Cause**: Database connections used across different event loops

**Solution**: Don't create new event loops in thread pools. Use the main event loop for all async operations.

### Stuck Operations

**Symptom**: Frontend shows "analyzing" but database shows "completed"

**Cause**: WebSocket message missed, frontend state not cleared

**Solution**: Frontend polling (every 5 seconds) will auto-correct by checking database state and clearing non-running operations.

## Coding Standards

- **Comments**: Use English only. No Korean or other non-English text.
- **Error Messages**: Provide detailed, actionable error messages
- **Type Hints**: Use Python type hints for function signatures
- **Async/Await**: Always use async/await for I/O operations
- **Session Management**: Always use `async with` for database sessions or ensure proper cleanup in finally blocks
