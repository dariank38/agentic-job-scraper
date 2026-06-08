"""电鸭社区 post parser for extracting full content."""

import logging
from typing import Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def parse_eleduck_post(page: Page, post_url: str) -> dict[str, Any]:
    """Parse a 电鸭 post detail page to extract full content.

    Args:
        page: Playwright page instance.
        post_url: URL of the post detail page.

    Returns:
        Dictionary with post content including title, author, full text, etc.
    """
    try:
        await page.goto(post_url, wait_until="networkidle")

        # Wait for content to load
        await page.wait_for_selector(".post-detail", timeout=10000)

        # Extract title
        title_elem = await page.query_selector(".post-detail-title")
        title = await title_elem.inner_text() if title_elem else None

        # Extract author
        author_elem = await page.query_selector(".post-detail-author .name")
        author = await author_elem.inner_text() if author_elem else None

        # Extract full text
        content_elem = await page.query_selector(".post-detail-content")
        text = await content_elem.inner_text() if content_elem else None

        # Extract tags
        tags = []
        tag_elements = await page.query_selector_all(".post-detail-tags .tag")
        for tag_elem in tag_elements:
            tag_text = await tag_elem.inner_text()
            tags.append(tag_text)

        return {
            "title": title,
            "author": author,
            "text": text,
            "tags": tags,
            "url": post_url,
        }

    except Exception as e:
        logger.error(f"[ELEDUCK PARSER] Error parsing {post_url}: {e}", exc_info=True)
        return {
            "title": None,
            "author": None,
            "text": None,
            "tags": [],
            "url": post_url,
        }
