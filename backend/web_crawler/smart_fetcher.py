"""Smart website fetcher with multi-strategy approach: RSS → Static → Playwright."""

import httpx
import feedparser
import trafilatura
import logging
from typing import Optional, Any
from playwright.async_api import async_playwright

from web_crawler.config import HEADLESS, TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

RSS_PATHS = ["/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml"]


class SmartSiteCrawler:
    """Smart crawler that tries RSS first, then static HTML, then Playwright."""

    async def fetch(self, url: str) -> dict[str, Any]:
        """Fetch content from URL using best available method.

        Args:
            url: The URL to fetch from.

        Returns:
            Dictionary with 'type' (rss, html, playwright) and 'content'.
        """
        logger.info(f"[SMART FETCH] Starting: {url}")

        # 1. Try RSS first (cleanest structured data)
        rss = await self._try_rss(url)
        if rss:
            logger.info(f"[SMART FETCH] Using RSS for {url}")
            return {"type": "rss", "content": rss}

        # 2. Try static HTML with trafilatura (clean content extraction)
        html = await self._fetch_static(url)
        if html:
            text = trafilatura.extract(html, include_links=True, include_comments=False)
            if text and len(text) > 100:  # Minimum content threshold
                logger.info(f"[SMART FETCH] Using static HTML for {url}")
                return {"type": "html", "content": text}

        # 3. Fallback to Playwright (JS-heavy sites)
        logger.info(f"[SMART FETCH] Using Playwright for {url}")
        text = await self._fetch_playwright(url)
        return {"type": "playwright", "content": text}

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
                            for e in feed.entries[:20]:  # Limit to 20 entries
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

    async def _fetch_static(self, url: str) -> Optional[str]:
        """Fetch static HTML content.

        Args:
            url: URL to fetch.

        Returns:
            HTML string if successful, None otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                if r.status_code == 200:
                    return r.text
        except Exception as e:
            logger.debug(f"[STATIC] Failed for {url}: {e}")
        return None

    async def _fetch_playwright(self, url: str) -> str:
        """Fetch content using Playwright for JS-rendered pages.

        Args:
            url: URL to fetch.

        Returns:
            Text content of the page.
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=HEADLESS)
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                page.set_default_timeout(TIMEOUT)

                await page.goto(url, wait_until="networkidle")
                content = await page.inner_text("body")

                await context.close()
                await browser.close()

                return content
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] Failed for {url}: {e}", exc_info=True)
            return ""
