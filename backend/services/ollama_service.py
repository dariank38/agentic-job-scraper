"""Async Ollama/NVIDIA service — thin re-export hub for backward compatibility.

Implementation is split across:
  services/language.py        — Language enum + detect_language()
  services/message_filter.py  — SYSTEM_PROMPT, should_analyze_message()
  services/ollama_analyzer.py — AsyncOllamaAnalyzer
  services/nvidia_analyzer.py — AsyncNvidiaAnalyzer
"""

import logging
import os

from services.language import Language, detect_language
from services.message_filter import SYSTEM_PROMPT, should_analyze_message
from services.ollama_analyzer import AsyncOllamaAnalyzer, RECOMMENDED_MODEL
from services.nvidia_analyzer import AsyncNvidiaAnalyzer, NVIDIA_API_KEY, NVIDIA_INVOKE_URL, NVIDIA_ANALYZE_MODEL

from telegram_processor.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def is_ollama_available() -> bool:
    """Returns True if the configured analyze provider is reachable."""
    import asyncio
    from app.routes.settings import get_analyze_provider
    if get_analyze_provider() == "nvidia":
        if not NVIDIA_API_KEY:
            logger.error("[PROVIDER] ANALYZE_PROVIDER=nvidia but NVIDIA_API_KEY is not set")
            return False
        return True
    try:
        from ollama import AsyncClient
        client = AsyncClient(host=OLLAMA_BASE_URL)
        await asyncio.wait_for(client.list(), timeout=5)
        return True
    except Exception:
        return False


_ollama_analyzer = AsyncOllamaAnalyzer()
_nvidia_analyzer = AsyncNvidiaAnalyzer()


def get_analyzer():
    """Return the analyzer instance based on runtime ANALYZE_PROVIDER config."""
    from app.routes.settings import get_analyze_provider
    if get_analyze_provider() == "nvidia":
        return _nvidia_analyzer
    return _ollama_analyzer