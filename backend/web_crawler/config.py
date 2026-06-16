"""Configuration management for the website crawler."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent

# Fetcher settings
DEFAULT_BATCH_SIZE = 20
DEFAULT_BATCH_DELAY = 2.0  # seconds
DEFAULT_DAYS_BACK = 7

# User agent
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Playwright settings
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))  # milliseconds
