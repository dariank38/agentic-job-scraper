"""Runtime settings API — allows changing AI provider without restarting. Persists to disk."""

import json
import logging
import os
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from telegram_processor.config import (
    ANALYZE_PROVIDER as _DEFAULT_ANALYZE,
    RESUME_PROVIDER as _DEFAULT_RESUME,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

logger = logging.getLogger(__name__)

_VALID_PROVIDERS = {"ollama", "nvidia"}
_SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings.json"

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "qwen/qwen3.5-397b-a17b")


def _load_from_disk() -> dict:
    """Load persisted settings, falling back to env/config defaults."""
    defaults = {
        "analyze_provider": _DEFAULT_ANALYZE,
        "resume_provider": _DEFAULT_RESUME,
        "nvidia_model": NVIDIA_MODEL,
    }
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text())
            # Only accept known valid values; ignore anything corrupt
            for key in ("analyze_provider", "resume_provider"):
                val = data.get(key, "").lower()
                if val in _VALID_PROVIDERS:
                    defaults[key] = val
            if data.get("nvidia_model"):
                defaults["nvidia_model"] = data["nvidia_model"]
            logger.info("[SETTINGS] Loaded from %s: %s", _SETTINGS_FILE, defaults)
    except Exception as e:
        logger.warning("[SETTINGS] Could not read %s, using defaults: %s", _SETTINGS_FILE, e)
    return defaults


def _save_to_disk(data: dict) -> None:
    """Persist current settings to disk."""
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning("[SETTINGS] Could not write %s: %s", _SETTINGS_FILE, e)


# Load on module import (i.e. at startup)
_runtime: dict = _load_from_disk()


def get_analyze_provider() -> str:
    return _runtime["analyze_provider"]


def get_resume_provider() -> str:
    return _runtime["resume_provider"]


def get_nvidia_model() -> str:
    return _runtime["nvidia_model"]


class ProvidersUpdate(BaseModel):
    analyze_provider: str | None = None
    resume_provider: str | None = None
    nvidia_model: str | None = None


def register_settings_routes(app):
    """Register settings API routes."""

    @app.get("/api/settings/providers")
    async def get_providers():
        """Return current runtime AI provider configuration."""
        return {
            "analyze_provider": _runtime["analyze_provider"],
            "resume_provider": _runtime["resume_provider"],
            "nvidia_api_key_configured": bool(NVIDIA_API_KEY),
            "ollama_base_url": OLLAMA_BASE_URL,
            "ollama_model": OLLAMA_MODEL,
            "nvidia_model": _runtime["nvidia_model"],
        }

    @app.put("/api/settings/providers")
    async def update_providers(body: ProvidersUpdate):
        """Update runtime AI provider configuration (persisted to disk)."""
        if body.analyze_provider is not None:
            val = body.analyze_provider.lower()
            if val not in _VALID_PROVIDERS:
                raise HTTPException(status_code=400, detail=f"Invalid analyze_provider '{val}'. Must be 'ollama' or 'nvidia'.")
            if val == "nvidia" and not NVIDIA_API_KEY:
                raise HTTPException(status_code=400, detail="Cannot set analyze_provider=nvidia: NVIDIA_API_KEY is not configured.")
            _runtime["analyze_provider"] = val

        if body.resume_provider is not None:
            val = body.resume_provider.lower()
            if val not in _VALID_PROVIDERS:
                raise HTTPException(status_code=400, detail=f"Invalid resume_provider '{val}'. Must be 'ollama' or 'nvidia'.")
            if val == "nvidia" and not NVIDIA_API_KEY:
                raise HTTPException(status_code=400, detail="Cannot set resume_provider=nvidia: NVIDIA_API_KEY is not configured.")
            _runtime["resume_provider"] = val

        if body.nvidia_model is not None:
            val = body.nvidia_model.strip()
            if not val:
                raise HTTPException(status_code=400, detail="nvidia_model cannot be empty.")
            _runtime["nvidia_model"] = val

        _save_to_disk(_runtime)
        logger.info(
            "[SETTINGS] Saved: analyze=%s resume=%s nvidia_model=%s",
            _runtime["analyze_provider"], _runtime["resume_provider"], _runtime["nvidia_model"],
        )

        return {
            "analyze_provider": _runtime["analyze_provider"],
            "resume_provider": _runtime["resume_provider"],
            "nvidia_model": _runtime["nvidia_model"],
        }
