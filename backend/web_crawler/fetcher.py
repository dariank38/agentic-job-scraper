"""Website post fetcher using Playwright for dynamic sites."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from playwright.async_api import async_playwright, Browser, Page

from web_crawler.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_DELAY,
    HEADLESS,
    TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


async def fetch_posts(
    url: str,
    site_type: str,
    days_back: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
) -> list[dict[str, Any]]:
    """Fetch posts from a website with batch processing.

    Args:
        url: The website URL to fetch from.
        site_type: The site type (e.g., 'v2ex', 'eleduck') for parser selection.
        days_back: Extra days before today to include (0 = today only).
        batch_size: Posts per page/batch (default: 20).
        batch_delay: Seconds to wait between batches (default: 2.0).

    Returns:
        List of post dictionaries.
    """
    posts: list[dict[str, Any]] = []

    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today_midnight - timedelta(days=days_back)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            page.set_default_timeout(TIMEOUT)

            # Navigate to the URL
            logger.info(f"[FETCH] Navigating to {url}")
            await page.goto(url, wait_until="networkidle")

            # Site-specific parsing
            if site_type == "v2ex":
                posts = await _fetch_v2ex_posts(page, cutoff_date, batch_size, batch_delay)
            elif site_type == "eleduck":
                posts = await _fetch_eleduck_posts(page, cutoff_date, batch_size, batch_delay)
            else:
                logger.error(f"[FETCH] Unknown site type: {site_type}")

            await context.close()
            await browser.close()

    except Exception as e:
        logger.error(f"[FETCH] Error fetching from {url}: {e}", exc_info=True)

    return posts


async def _fetch_v2ex_posts(
    page: Page,
    cutoff_date: datetime,
    batch_size: int,
    batch_delay: float,
) -> list[dict[str, Any]]:
    """Fetch posts from V2EX.

    Args:
        page: Playwright page instance.
        cutoff_date: Date cutoff for posts.
        batch_size: Posts per page.
        batch_delay: Delay between pages.

    Returns:
        List of post dictionaries.
    """
    posts: list[dict[str, Any]] = []
    page_num = 1
    reached_cutoff = False

    try:
        while not reached_cutoff:
            logger.info(f"[FETCH V2EX] Page {page_num}")

            # Wait for posts to load
            await page.wait_for_selector(".item", timeout=10000)

            # Extract posts
            post_elements = await page.query_selector_all(".item")
            batch_count = 0

            for element in post_elements:
                if batch_count >= batch_size:
                    break

                try:
                    # Extract post data
                    title_elem = await element.query_selector(".topic-link")
                    post_id = await element.get_attribute("data-id")
                    title = await title_elem.inner_text() if title_elem else None

                    # Extract date
                    date_elem = await element.query_selector(".ago")
                    date_text = await date_elem.inner_text() if date_elem else None
                    post_date = _parse_v2ex_date(date_text) if date_text else None

                    # Extract author
                    author_elem = await element.query_selector(".user-name")
                    author = await author_elem.inner_text() if author_elem else None

                    # Extract URL
                    post_url = await title_elem.get_attribute("href") if title_elem else None
                    if post_url and not post_url.startswith("http"):
                        post_url = f"https://v2ex.com{post_url}"

                    # Check cutoff
                    if post_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break

                    if title and post_id:
                        posts.append({
                            "id": post_id,
                            "title": title,
                            "url": post_url,
                            "author": author,
                            "date": post_date,
                            "text": title,  # V2EX posts need detail page fetch for full text
                        })
                        batch_count += 1

                except Exception as e:
                    logger.warning(f"[FETCH V2EX] Error parsing post: {e}")
                    continue

            # Check if we need to go to next page
            if batch_count < batch_size or reached_cutoff:
                break

            # Look for next page button
            next_button = await page.query_selector(".page_normal:last-child")
            if next_button:
                await next_button.click()
                await asyncio.sleep(batch_delay)
                page_num += 1
            else:
                break

    except Exception as e:
        logger.error(f"[FETCH V2EX] Error: {e}", exc_info=True)

    return posts


async def _fetch_eleduck_posts(
    page: Page,
    cutoff_date: datetime,
    batch_size: int,
    batch_delay: float,
) -> list[dict[str, Any]]:
    """Fetch posts from 电鸭社区.

    Args:
        page: Playwright page instance.
        cutoff_date: Date cutoff for posts.
        batch_size: Posts per page.
        batch_delay: Delay between pages.

    Returns:
        List of post dictionaries.
    """
    posts: list[dict[str, Any]] = []
    page_num = 1
    reached_cutoff = False

    try:
        while not reached_cutoff:
            logger.info(f"[FETCH ELEDUCK] Page {page_num}")

            # Wait for posts to load
            await page.wait_for_selector(".post-item", timeout=10000)

            # Extract posts
            post_elements = await page.query_selector_all(".post-item")
            batch_count = 0

            for element in post_elements:
                if batch_count >= batch_size:
                    break

                try:
                    # Extract post data
                    title_elem = await element.query_selector(".post-title a")
                    title = await title_elem.inner_text() if title_elem else None

                    # Extract post ID from URL
                    post_url = await title_elem.get_attribute("href") if title_elem else None
                    post_id = post_url.split("/")[-1] if post_url else None

                    # Extract date
                    date_elem = await element.query_selector(".post-meta .time")
                    date_text = await date_elem.inner_text() if date_elem else None
                    post_date = _parse_eleduck_date(date_text) if date_text else None

                    # Extract author
                    author_elem = await element.query_selector(".post-meta .author")
                    author = await author_elem.inner_text() if author_elem else None

                    # Check cutoff
                    if post_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break

                    if title and post_id:
                        posts.append({
                            "id": post_id,
                            "title": title,
                            "url": post_url,
                            "author": author,
                            "date": post_date,
                            "text": title,  # 电鸭 posts need detail page fetch for full text
                        })
                        batch_count += 1

                except Exception as e:
                    logger.warning(f"[FETCH ELEDUCK] Error parsing post: {e}")
                    continue

            # Check if we need to go to next page
            if batch_count < batch_size or reached_cutoff:
                break

            # Look for next page button
            next_button = await page.query_selector(".pagination .next")
            if next_button:
                await next_button.click()
                await asyncio.sleep(batch_delay)
                page_num += 1
            else:
                break

    except Exception as e:
        logger.error(f"[FETCH ELEDUCK] Error: {e}", exc_info=True)

    return posts


def _parse_v2ex_date(date_text: str) -> datetime:
    """Parse V2EX date string (e.g., "2小时前", "3天前").

    Args:
        date_text: Date string from V2EX.

    Returns:
        Datetime object.
    """
    now = datetime.now(timezone.utc)

    if "分钟前" in date_text:
        minutes = int(date_text.replace("分钟前", ""))
        return now - timedelta(minutes=minutes)
    elif "小时前" in date_text:
        hours = int(date_text.replace("小时前", ""))
        return now - timedelta(hours=hours)
    elif "天前" in date_text:
        days = int(date_text.replace("天前", ""))
        return now - timedelta(days=days)
    else:
        # Try to parse as regular date
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except:
            return now


def _parse_eleduck_date(date_text: str) -> datetime:
    """Parse 电鸭 date string (e.g., "2小时前", "3天前").

    Args:
        date_text: Date string from 电鸭.

    Returns:
        Datetime object.
    """
    now = datetime.now(timezone.utc)

    if "分钟前" in date_text:
        minutes = int(date_text.replace("分钟前", ""))
        return now - timedelta(minutes=minutes)
    elif "小时前" in date_text:
        hours = int(date_text.replace("小时前", ""))
        return now - timedelta(hours=hours)
    elif "天前" in date_text:
        days = int(date_text.replace("天前", ""))
        return now - timedelta(days=days)
    else:
        # Try to parse as regular date
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except:
            return now
