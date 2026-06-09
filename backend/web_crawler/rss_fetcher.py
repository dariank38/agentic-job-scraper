"""RSS fetcher for job postings."""

import httpx
import feedparser
import logging
from typing import Optional, Any

from web_crawler.config import USER_AGENT

logger = logging.getLogger(__name__)


class Fetcher:
    """Generic RSS crawler for job postings."""

    async def fetch(self, url: str) -> dict[str, Any]:
        """Fetch RSS feed content.

        Args:
            url: The RSS feed URL to fetch.

        Returns:
            Dictionary with 'type' (rss) and 'content' (list of RSS entries).
        """
        logger.info(f"[RSS FETCH] Fetching from {url}")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                if r.status_code == 200:
                    feed = feedparser.parse(r.text)
                    if feed.entries:
                        entries = []
                        for e in feed.entries[:50]:  # Limit to 50 entries
                            entry_text = f"Title: {e.get('title', '')}\n"
                            entry_text += f"Summary: {e.get('summary', '')}\n"
                            entry_text += f"Link: {e.get('link', '')}\n"
                            entry_text += f"Published: {e.get('published', '')}\n"
                            entries.append(entry_text)
                        logger.info(f"[RSS FETCH] Found {len(entries)} entries")
                        return {"type": "rss", "content": entries}
                    else:
                        logger.error(f"[RSS FETCH] No entries found in feed")
                        return {"type": "rss", "content": []}
                else:
                    logger.error(f"[RSS FETCH] HTTP {r.status_code} for {url}")
                    return {"type": "rss", "content": []}
        except Exception as e:
            logger.error(f"[RSS FETCH] Error fetching {url}: {e}")
            return {"type": "rss", "content": []}
