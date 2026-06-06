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

# Telegram settings (required)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
if TELEGRAM_API_ID == 0:
    raise ValueError("TELEGRAM_API_ID environment variable is required")

TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
if not TELEGRAM_API_HASH:
    raise ValueError("TELEGRAM_API_HASH environment variable is required")

TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
if not TELEGRAM_PHONE:
    raise ValueError("TELEGRAM_PHONE environment variable is required")

TELEGRAM_SESSION_PATH = SESSION_DIR / "telegram.session"

# Ollama settings (optional - will be checked at runtime)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Fetcher settings
DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_DELAY = 1.0  # seconds
DEFAULT_DAYS_BACK = 10

# Rate limiting
FLOOD_WAIT_RETRY = True
