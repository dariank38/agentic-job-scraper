"""Configuration management for the job scraper."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
SESSION_DIR = BASE_DIR / "session"

# Ensure directories exist
SESSION_DIR.mkdir(exist_ok=True)

# Database (required)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Telegram settings (optional - now stored in database for multi-account support)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_SESSION_PATH = SESSION_DIR / "telegram.session"

# Ollama settings (optional - will be checked at runtime)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Fetcher settings
DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_DELAY = 1.0  # seconds
DEFAULT_DAYS_BACK = 15

# Rate limiting
FLOOD_WAIT_RETRY = True
