"""Self-healing Playwright scraper with selector recovery and fingerprint rotation."""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Callable, Optional

from playwright.async_api import async_playwright, TimeoutError, Error as PlaywrightError

from app.autonomous.budget_guard import OllamaBudgetGuard
from app.autonomous.state_manager import AutonomousStateManager
from services.ollama_service import AsyncOllamaAnalyzer

logger = logging.getLogger(__name__)


class ScraperFailure(Exception):
    """Raised when all self-healing strategies fail."""

    def __init__(self, message: str, last_error: Optional[str] = None):
        super().__init__(message)
        self.last_error = last_error


@dataclass
class Fingerprint:
    """Browser fingerprint for anti-bot rotation."""

    user_agent: str
    viewport: dict
    locale: str
    color_scheme: str = "light"


class FingerprintRotator:
    """Rotate browser fingerprints to reduce detection."""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    ]

    VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
    ]

    LOCALES = ["en-US", "en-GB", "zh-CN", "zh-TW"]

    def __init__(self, state_manager: Optional[AutonomousStateManager] = None):
        self.state_manager = state_manager
        self._index = 0

    async def initialize(self) -> None:
        if self.state_manager:
            self._index = await self.state_manager.get("fingerprint_index", 0)

    def next(self) -> Fingerprint:
        fingerprint = Fingerprint(
            user_agent=random.choice(self.USER_AGENTS),
            viewport=random.choice(self.VIEWPORTS),
            locale=random.choice(self.LOCALES),
        )
        self._index += 1
        return fingerprint

    async def persist_index(self) -> None:
        if self.state_manager:
            await self.state_manager.set("fingerprint_index", self._index)


class SelectorRegistry:
    """Store and retrieve CSS selectors for specific site types."""

    def __init__(self, state_manager: Optional[AutonomousStateManager] = None):
        self.state_manager = state_manager
        self._registry: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        if self.state_manager:
            self._registry = await self.state_manager.get("selector_registry", {})

    def get(self, site_type: str) -> dict[str, Any]:
        return self._registry.get(site_type, {})

    async def update(self, site_type: str, selectors: dict[str, Any]) -> None:
        self._registry.setdefault(site_type, {}).update(selectors)
        if self.state_manager:
            await self.state_manager.merge("selector_registry", {site_type: selectors})


class SelfHealingScraper:
    """Adaptive Playwright wrapper that heals on failure.

    Failure taxonomy:
        - TimeoutError: retry with longer wait and scroll.
        - 403/Cloudflare: rotate proxy and fingerprint.
        - Missing selector: ask LLM to identify new selectors from HTML.
        - Stale element: re-evaluate via JavaScript.
    """

    def __init__(
        self,
        analyzer: AsyncOllamaAnalyzer,
        budget_guard: OllamaBudgetGuard,
        state_manager: Optional[AutonomousStateManager] = None,
        proxy_pool: Optional[list[str]] = None,
        max_attempts: int = 3,
    ):
        self.analyzer = analyzer
        self.budget_guard = budget_guard
        self.state_manager = state_manager
        self.proxy_pool = proxy_pool or []
        self.max_attempts = max(1, max_attempts)
        self.fingerprint_rotator = FingerprintRotator(state_manager)
        self.selector_registry = SelectorRegistry(state_manager)

    async def initialize(self) -> None:
        await self.fingerprint_rotator.initialize()
        await self.selector_registry.initialize()
        if self.state_manager:
            await self.budget_guard.initialize()

    async def scrape(
        self,
        url: str,
        site_type: str,
        extraction_fn: Optional[Callable] = None,
        html_sample_size: int = 8000,
    ) -> Any:
        """Scrape URL with self-healing retries.

        Args:
            url: Target URL.
            site_type: Identifier for selector registry (e.g., 'bossjob').
            extraction_fn: Optional async function(page) -> result.
            html_sample_size: Max characters of HTML sent to LLM for healing.
        """
        last_error: Optional[str] = None

        for attempt in range(self.max_attempts):
            proxy = random.choice(self.proxy_pool) if self.proxy_pool else None
            fingerprint = self.fingerprint_rotator.next()

            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        proxy={"server": proxy} if proxy else None,
                    )
                    context = await browser.new_context(
                        user_agent=fingerprint.user_agent,
                        viewport=fingerprint.viewport,
                        locale=fingerprint.locale,
                        color_scheme=fingerprint.color_scheme,
                    )
                    page = await context.new_page()

                    try:
                        result = await self._execute_with_fallbacks(
                            page, url, site_type, extraction_fn, html_sample_size
                        )
                        await self.fingerprint_rotator.persist_index()
                        return result
                    finally:
                        await context.close()
                        await browser.close()

            except ScraperFailure:
                raise
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "[SELF HEALING] Attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self.max_attempts,
                    url,
                    last_error,
                )
                if attempt < self.max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)

        await self.fingerprint_rotator.persist_index()
        raise ScraperFailure(
            f"Failed to scrape {url} after {self.max_attempts} attempts",
            last_error=last_error,
        )

    async def _execute_with_fallbacks(
        self,
        page,
        url: str,
        site_type: str,
        extraction_fn: Optional[Callable],
        html_sample_size: int,
    ) -> Any:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            if extraction_fn:
                return await extraction_fn(page)

            # Default behavior: extract text and selector registry
            return await self._default_extract(page, site_type)

        except TimeoutError:
            logger.info("[SELF HEALING] DOM timeout, scrolling and retrying")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            if extraction_fn:
                return await extraction_fn(page)
            return await self._default_extract(page, site_type)

        except PlaywrightError as e:
            error_message = str(e).lower()
            if "selector" in error_message or "element" in error_message:
                logger.info("[SELF HEALING] Selector error, attempting LLM healing")
                return await self._heal_and_retry(
                    page, site_type, extraction_fn, html_sample_size
                )
            raise

    async def _heal_and_retry(
        self,
        page,
        site_type: str,
        extraction_fn: Optional[Callable],
        html_sample_size: int,
    ) -> Any:
        """Use LLM to identify new selectors and retry extraction."""
        html = await page.content()
        sample = html[:html_sample_size]
        estimated = self.budget_guard.estimate_tokens(sample)

        if not await self.budget_guard.check(estimated):
            logger.warning("[SELF HEALING] Ollama budget exhausted, cannot heal selectors")
            raise ScraperFailure("Ollama budget exhausted for selector healing")

        prompt = f"""You are a web scraping expert. The scraper for site type '{site_type}' failed to find its expected DOM selectors.
Here is a sample of the current HTML:

```html
{sample}
```

Identify the most robust CSS selectors for:
1. job title container
2. job description container
3. job requirements container
4. company name
5. job URL / apply link
6. location

Return strictly JSON, no markdown, no explanation:
{{
    "job_title": "selector",
    "job_description": "selector",
    "job_requirements": "selector",
    "company_name": "selector",
    "job_url": "selector",
    "location": "selector"
}}
"""

        try:
            result = await self.analyzer.analyze_message(prompt)
            await self.budget_guard.record_usage(
                prompt_tokens=estimated,
                completion_tokens=self.budget_guard.estimate_tokens(str(result)),
            )

            if isinstance(result, dict) and any(result.values()):
                await self.selector_registry.update(site_type, result)
                logger.info("[SELF HEALING] Healed selectors for %s: %s", site_type, result)
                if extraction_fn:
                    return await extraction_fn(page)
                return await self._default_extract(page, site_type)
            else:
                logger.warning("[SELF HEALING] LLM returned unusable selectors")
                raise ScraperFailure("LLM selector healing returned unusable selectors")
        except Exception as e:
            logger.error("[SELF HEALING] Error during healing: %s", e)
            raise ScraperFailure(f"Healing failed: {e}")

    async def _default_extract(self, page, site_type: str) -> dict[str, Any]:
        """Default extraction using registry or fallback to page text."""
        selectors = self.selector_registry.get(site_type)
        result: dict[str, Any] = {}

        for key, selector in selectors.items():
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    result[key] = text.strip()
            except Exception:
                pass

        if not result:
            # Fallback: extract all visible text from the page
            result["page_text"] = await page.evaluate(
                "() => document.body.innerText.trim().slice(0, 5000)"
            )

        return result
