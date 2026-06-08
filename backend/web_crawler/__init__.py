"""Website crawler module for job boards."""

from web_crawler.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_DELAY,
    DEFAULT_DAYS_BACK,
    USER_AGENT,
)
from web_crawler.fetcher import fetch_posts
from web_crawler.smart_fetcher import SmartSiteCrawler
from web_crawler.smart_extractor import SmartOllamaExtractor
from web_crawler.models import ExtractedData, JobPosting, DeveloperInfo, ContactInfo

__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_BATCH_DELAY",
    "DEFAULT_DAYS_BACK",
    "USER_AGENT",
    "fetch_posts",
    "SmartSiteCrawler",
    "SmartOllamaExtractor",
    "ExtractedData",
    "JobPosting",
    "DeveloperInfo",
    "ContactInfo",
]
