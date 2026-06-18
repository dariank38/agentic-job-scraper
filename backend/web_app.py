"""FastAPI API application for job scraper."""

import logging
import sys
from pathlib import Path

# Fix Windows console encoding for Chinese/emoji characters (must be before logging setup)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configure colored logging
log_file = Path(__file__).parent / "app.log"
from colored_logging import setup_colored_logging
setup_colored_logging(str(log_file))
logging.info(f"Logging to file: {log_file}")

# Suppress noisy websockets disconnect tracebacks (normal when clients close connection)
logging.getLogger("websockets").setLevel(logging.WARNING)

class _SuppressWsDisconnect(logging.Filter):
    """Drop uvicorn 'data transfer failed' / WinError 121 records — harmless client disconnects."""
    _SUPPRESS = ("data transfer failed", "WinError 121", "WinError 64")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if any(s in msg for s in self._SUPPRESS):
            return False
        if record.exc_info:
            import traceback
            tb = "".join(traceback.format_exception(*record.exc_info))
            if any(s in tb for s in self._SUPPRESS):
                return False
        return True

logging.getLogger("uvicorn.error").addFilter(_SuppressWsDisconnect())
logging.getLogger("uvicorn").addFilter(_SuppressWsDisconnect())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.tasks import lifespan
from app.api_routes import register_api_routes

app = FastAPI(
    title="Telegram Job Scraper API",
    description="API for scraping and analyzing Telegram job postings",
    lifespan=lifespan,
)

# Add CORS middleware - update for production domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
register_api_routes(app)

# Mount static files from frontend build
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    # Mount only the assets directory (JS/CSS bundles)
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve index.html for SPA routes (non-API paths only)
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # Never intercept API or WebSocket routes
        if path.startswith("api/") or path.startswith("ws/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        file_path = frontend_dist / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
