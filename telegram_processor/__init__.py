"""Telegram Processor - Core Telegram scraping and analysis.

This package provides tools for:
- Fetching messages from Telegram channels
- Analyzing job postings using local LLM (Ollama)
- Extracting job details, contact info, and remote work opportunities
"""

__version__ = "0.1.0"

from telegram_processor.config import *
from telegram_processor.client import TelegramClientManager
from telegram_processor.fetcher import fetch_messages
from telegram_processor.ollama import analyze_message, is_ollama_available

__all__ = [
    "config",
    "TelegramClientManager",
    "fetch_messages",
    "analyze_message",
    "is_ollama_available",
]
