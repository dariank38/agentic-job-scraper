"""Website post fetcher using Playwright for dynamic sites.


Bossjob-specific logic lives in web_crawler/bossjob_fetcher.py.
"""


import asyncio

import logging

from datetime import datetime, timedelta, timezone

from typing import Any, Optional

from playwright.async_api import async_playwright, Page

from web_crawler.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_DELAY,
    HEADLESS,
    TIMEOUT,
    USER_AGENT,
)

from services.ollama_service import AsyncOllamaAnalyzer

from web_crawler.bossjob_fetcher import fetch_bossjob_posts as _fetch_bossjob_posts


logger = logging.getLogger(__name__)


async def fetch_posts(
    url: str,
    site_type: str,
    days_back: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
    cookies: list[dict] | None = None,
    analyzer: Optional[AsyncOllamaAnalyzer] = None,
) -> list[dict[str, Any]]:
    """Fetch posts from a website with batch processing."""
    posts: list[dict[str, Any]] = []

    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today_midnight - timedelta(days=days_back)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1920, "height": 1080})
            if cookies:
                await context.add_cookies(cookies)
                logger.info(f"[FETCH] Added {len(cookies)} cookies for authentication")
            page = await context.new_page()
            page_timeout = 120000 if site_type == "bossjob" else TIMEOUT
            page.set_default_timeout(page_timeout)
            logger.info(f"[FETCH] Navigating to {url}")
            wait_until = "commit" if site_type == "bossjob" else "networkidle"
            await page.goto(url, wait_until=wait_until, timeout=page_timeout)
            if site_type == "v2ex":
                posts = await _fetch_v2ex_posts(page, cutoff_date, batch_size, batch_delay)
            elif site_type == "eleduck":
                posts = await _fetch_eleduck_posts(page, cutoff_date, batch_size, batch_delay)
            elif site_type == "bossjob":
                posts = await _fetch_bossjob_posts(page, cutoff_date, batch_size, batch_delay)
            else:
                logger.error(f"[FETCH] Unknown site type: {site_type}")
            await context.close()
            await browser.close()
    except Exception as e:
        logger.error(f"[FETCH] Error fetching from {url}: {e}", exc_info=True)

    return posts


async def _fetch_v2ex_posts(page: Page, cutoff_date: datetime, batch_size: int, batch_delay: float) -> list[dict[str, Any]]:
    """Fetch posts from V2EX."""
    posts: list[dict[str, Any]] = []
    page_num = 1
    reached_cutoff = False

    try:
        while not reached_cutoff:
            logger.info(f"[FETCH V2EX] Page {page_num}")
            await page.wait_for_selector(".item", timeout=10000)
            post_elements = await page.query_selector_all(".item")
            batch_count = 0

            for element in post_elements:
                if batch_count >= batch_size:
                    break
                try:
                    title_elem = await element.query_selector(".topic-link")
                    post_id = await element.get_attribute("data-id")
                    title = await title_elem.inner_text() if title_elem else None
                    date_elem = await element.query_selector(".ago")
                    date_text = await date_elem.inner_text() if date_elem else None
                    post_date = _parse_v2ex_date(date_text) if date_text else None
                    author_elem = await element.query_selector(".user-name")
                    author = await author_elem.inner_text() if author_elem else None
                    post_url = await title_elem.get_attribute("href") if title_elem else None
                    if post_url and not post_url.startswith("http"):
                        post_url = f"https://v2ex.com{post_url}"
                    if post_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break
                    if title and post_id:
                        posts.append({"id": post_id, "title": title, "url": post_url, "author": author, "date": post_date, "text": title})
                        batch_count += 1
                except Exception as e:
                    logger.warning(f"[FETCH V2EX] Error parsing post: {e}")
                    continue

            if batch_count < batch_size or reached_cutoff:
                break
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


async def _fetch_eleduck_posts(page: Page, cutoff_date: datetime, batch_size: int, batch_delay: float) -> list[dict[str, Any]]:
    """Fetch posts from 电鸭社区."""
    posts: list[dict[str, Any]] = []
    page_num = 1
    reached_cutoff = False

    try:
        while not reached_cutoff:
            logger.info(f"[FETCH ELEDUCK] Page {page_num}")
            await page.wait_for_selector(".post-item", timeout=10000)
            post_elements = await page.query_selector_all(".post-item")
            batch_count = 0

            for element in post_elements:
                if batch_count >= batch_size:
                    break
                try:
                    title_elem = await element.query_selector(".post-title a")
                    title = await title_elem.inner_text() if title_elem else None
                    post_url = await title_elem.get_attribute("href") if title_elem else None
                    post_id = post_url.split("/")[-1] if post_url else None
                    date_elem = await element.query_selector(".post-meta .time")
                    date_text = await date_elem.inner_text() if date_elem else None
                    post_date = _parse_eleduck_date(date_text) if date_text else None
                    author_elem = await element.query_selector(".post-meta .author")
                    author = await author_elem.inner_text() if author_elem else None
                    if post_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break
                    if title and post_id:
                        posts.append({"id": post_id, "title": title, "url": post_url, "author": author, "date": post_date, "text": title})
                        batch_count += 1
                except Exception as e:
                    logger.warning(f"[FETCH ELEDUCK] Error parsing post: {e}")
                    continue

            if batch_count < batch_size or reached_cutoff:
                break
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
    now = datetime.now(timezone.utc)
    if "分钟前" in date_text:
        return now - timedelta(minutes=int(date_text.replace("分钟前", "")))
    elif "小时前" in date_text:
        return now - timedelta(hours=int(date_text.replace("小时前", "")))
    elif "天前" in date_text:
        return now - timedelta(days=int(date_text.replace("天前", "")))
    else:
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return now


def _parse_eleduck_date(date_text: str) -> datetime:
    now = datetime.now(timezone.utc)
    if "分钟前" in date_text:
        return now - timedelta(minutes=int(date_text.replace("分钟前", "")))
    elif "小时前" in date_text:
        return now - timedelta(hours=int(date_text.replace("小时前", "")))
    elif "天前" in date_text:
        return now - timedelta(days=int(date_text.replace("天前", "")))
    else:
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return now
