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
                            # Prefer full content over summary
                            content = ''
                            if e.get('content'):
                                content = e['content'][0].get('value', '') if isinstance(e['content'], list) else str(e['content'])
                            elif e.get('summary'):
                                content = e.get('summary', '')
                            entry_text = f"Title: {e.get('title', '')}\n"
                            entry_text += f"Link: {e.get('link', '')}\n"
                            entry_text += f"Published: {e.get('published', '')}\n"
                            if content:
                                entry_text += f"Content: {content}\n"
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


class V2EXFetcher:
    """V2EX-specific RSS fetcher that extracts titles for batch analysis."""

    async def fetch_titles(self, url: str) -> dict[str, Any]:
        """Fetch V2EX RSS feed and extract titles for batch analysis.

        Args:
            url: The V2EX RSS feed URL.

        Returns:
            Dictionary with 'type' (v2ex) and 'entries' (list of {title, link, published}).
        """
        logger.info(f"[V2EX FETCH] Fetching from {url}")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                if r.status_code == 200:
                    feed = feedparser.parse(r.text)
                    if feed.entries:
                        entries = []
                        for e in feed.entries[:50]:  # Limit to 50 entries
                            entries.append({
                                "title": e.get('title', ''),
                                "link": e.get('link', ''),
                                "published": e.get('published', ''),
                            })
                        logger.info(f"[V2EX FETCH] Found {len(entries)} entries")
                        return {"type": "v2ex", "entries": entries}
                    else:
                        logger.error(f"[V2EX FETCH] No entries found in feed")
                        return {"type": "v2ex", "entries": []}
                else:
                    logger.error(f"[V2EX FETCH] HTTP {r.status_code} for {url}")
                    return {"type": "v2ex", "entries": []}
        except Exception as e:
            logger.error(f"[V2EX FETCH] Error fetching {url}: {e}")
            return {"type": "v2ex", "entries": []}
