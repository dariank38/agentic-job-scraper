"""Telegram Processor - Core Telegram scraping and analysis.


This package provides tools for:
- Fetching messages from Telegram channels
- Analyzing job postings using local LLM (Ollama)
- Extracting job details, contact info, and remote work opportunities
"""

__version__ = "0.1.0"

from telegram_processor.config import *
from telegram_processor.client import TelegramClientManager
from telegram_processor.fetcher import fetch_messages, get_dialogs

__all__ = [
    "config",
    "TelegramClientManager",
    "fetch_messages",
    "get_dialogs",
]
