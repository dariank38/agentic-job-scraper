"""Configuration management for the job scraper."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
SESSION_DIR = BASE_DIR / "session"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
SESSION_DIR.mkdir(exist_ok=True)

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Telegram settings
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_SESSION_PATH = SESSION_DIR / "telegram.session"

# Channels file
CHANNELS_FILE = DATA_DIR / "channels.txt"

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Analysis state
ANALYZED_STATE_FILE = SESSION_DIR / "analyzed_messages.json"

# Fetcher settings
DEFAULT_BATCH_SIZE = 50
DEFAULT_BATCH_DELAY = 1.0  # seconds
DEFAULT_DAYS_BACK = 10

# Rate limiting
FLOOD_WAIT_RETRY = True
