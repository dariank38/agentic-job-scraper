"""RSS fetcher for job postings."""

import httpx
import feedparser
import logging
from typing import Optional, Any

from web_crawler.config import USER_AGENT

logger = logging.getLogger(__name__)

RSS_PATHS = ["/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml"]


class Fetcher:
    """Generic RSS crawler for job postings."""

    async def fetch(self, url: str) -> dict[str, Any]:
        """Fetch RSS feed content.

        Args:
            url: The URL to fetch RSS from.

        Returns:
            Dictionary with 'type' (rss) and 'content' (list of RSS entries).
        """
        logger.info(f"[RSS FETCH] Fetching from {url}")

        rss = await self._try_rss(url)
        if rss:
            logger.info(f"[RSS FETCH] Found {len(rss)} entries")
            return {"type": "rss", "content": rss}
        else:
            logger.error(f"[RSS FETCH] No RSS feed found for {url}")
            return {"type": "rss", "content": []}

    async def _try_rss(self, url: str) -> Optional[list[str]]:
        """Try to fetch RSS feed from common paths.

        Args:
            url: Base URL to check for RSS feeds.

        Returns:
            List of RSS entry strings if found, None otherwise.
        """
        base = url.rstrip("/")
        for path in RSS_PATHS:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(base + path, headers={"User-Agent": USER_AGENT})
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
                            logger.info(f"[RSS] Found {len(entries)} entries at {base + path}")
                            return entries
            except Exception as e:
                logger.debug(f"[RSS] Failed for {base + path}: {e}")
                continue
        return None
