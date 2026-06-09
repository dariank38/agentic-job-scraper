"""Website crawler module for job boards."""

from web_crawler.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_DELAY,
    DEFAULT_DAYS_BACK,
    USER_AGENT,
)
from web_crawler.fetcher import fetch_posts
from web_crawler.rss_fetcher import Fetcher
from web_crawler.rss_extractor import Extractor
from web_crawler.models import ExtractedData, JobPosting, DeveloperInfo, ContactInfo

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_BATCH_DELAY",
    "DEFAULT_DAYS_BACK",
    "USER_AGENT",
    "fetch_posts",
    "Fetcher",
    "Extractor",
    "ExtractedData",
    "JobPosting",
    "DeveloperInfo",
    "ContactInfo",
]
