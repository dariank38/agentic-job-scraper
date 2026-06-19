"""Autonomous source discovery from tech aggregators and communities."""

import asyncio
import logging
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.autonomous.budget_guard import OllamaBudgetGuard
from app.autonomous.self_healing_scraper import SelfHealingScraper
from app.models import Channel, WebsiteSource
from services.ollama_service import AsyncOllamaAnalyzer

logger = logging.getLogger(__name__)


class SourceDiscoveryAgent:
    """Discover new Telegram channels, RSS feeds, and job boards automatically.

    Seeds:
        - Hacker News "Who is Hiring?" threads
        - Reddit job communities
        - GitHub trending (for tech signals, not job boards)

    Discovered candidates are validated by attempting to fetch a sample or parse
    a feed, then added to the database as inactive sources pending human review.
    """

    def __init__(
        self,
        db: AsyncSession,
        analyzer: Optional[AsyncOllamaAnalyzer] = None,
        budget_guard: Optional[OllamaBudgetGuard] = None,
        scraper: Optional[SelfHealingScraper] = None,
    ):
        self.db = db
        self.analyzer = analyzer
        self.budget_guard = budget_guard
        self.scraper = scraper

    async def scout(self) -> list[dict[str, Any]]:
        """Run weekly discovery across all seeds."""
        candidates: list[dict[str, Any]] = []

        # Note: Hacker News and Reddit scouting removed per user request
        # Autonomous system now focuses on optimizing existing sources (Telegram, Bossjob, Dianya, V2EX)
        # rather than discovering new external sources

        # Validate and register
        registered = []
        for candidate in candidates:
            if await self._validate(candidate):
                await self._register(candidate)
                registered.append(candidate)

        logger.info(
            "[SOURCE DISCOVERY] Registered %d/%d candidates",
            len(registered),
            len(candidates),
        )
        return registered

    async def _scout_hackernews(self) -> list[dict[str, Any]]:
        """Find job board links and Telegram channels in HN hiring threads."""
        url = "https://hn.algolia.com/api/v1/search?query=Who%20is%20hiring&tags=story&hitsPerPage=5"
        candidates: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            for hit in data.get("hits", []):
                title = hit.get("title", "")
                object_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                if "hiring" in title.lower():
                    comments = await self._fetch_hn_comments(hit.get("objectID"))
                    candidates.extend(await self._extract_sources_from_text(comments))
        except Exception as e:
            logger.warning("[SOURCE DISCOVERY] HN scout failed: %s", e)

        return candidates

    async def _fetch_hn_comments(self, story_id: str) -> str:
        url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=50"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            comments = [hit.get("text", "") for hit in data.get("hits", [])]
            return "\n".join(comments)
        except Exception as e:
            logger.warning("[SOURCE DISCOVERY] Failed to fetch HN comments: %s", e)
            return ""

    async def _scout_reddit(self) -> list[dict[str, Any]]:
        """Find job boards in Reddit hiring communities."""
        subreddits = ["forhire", "remotejs", "golangjobs", "pythonjobs", "devopsjobs"]
        candidates: list[dict[str, Any]] = []

        for subreddit in subreddits:
            url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=25"
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; AgenticJobBot/1.0)"},
                    )
                    response.raise_for_status()
                    data = response.json()

                posts = data.get("data", {}).get("children", [])
                texts = [f"{p['data'].get('title', '')}\n{p['data'].get('selftext', '')}" for p in posts]
                candidates.extend(await self._extract_sources_from_text("\n".join(texts)))
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning("[SOURCE DISCOVERY] Reddit scout failed for r/%s: %s", subreddit, e)

        return candidates

    async def _extract_sources_from_text(self, text: str) -> list[dict[str, Any]]:
        """Use LLM to extract job source URLs from aggregated text."""
        if not text or not self.analyzer or not self.budget_guard:
            return []

        sample = text[:6000]
        estimated = self.budget_guard.estimate_tokens(sample)
        if not await self.budget_guard.check(estimated):
            return []

        prompt = f"""You are scanning developer communities for new job sources.

Here are posts/comments from Hacker News or Reddit:

```
{sample}
```

Extract any job boards, Telegram channels, or websites where people post software engineering jobs.

Return a JSON array of objects:
[
    {{
        "name": "Human readable name",
        "url": "https://example.com",
        "type": "website|telegram|rss",
        "reason": "Why this is a job source"
    }}
]

If none are found, return an empty array []."""

        try:
            result = await self.analyzer.analyze_message(prompt)
            await self.budget_guard.record_usage(
                prompt_tokens=estimated,
                completion_tokens=self.budget_guard.estimate_tokens(str(result)),
            )
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
        except Exception as e:
            logger.warning("[SOURCE DISCOVERY] LLM extraction failed: %s", e)

        return []

    async def _validate(self, candidate: dict[str, Any]) -> bool:
        """Validate that a candidate source is reachable and job-related."""
        url = candidate.get("url", "")
        source_type = candidate.get("type", "website")

        if not url or not url.startswith(("http://", "https://", "t.me/")):
            return False

        if source_type == "telegram":
            return url.startswith("https://t.me/")

        if source_type == "rss":
            return await self._validate_rss(url)

        # website: try a quick HEAD request
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.head(url)
                return response.status_code < 400
        except Exception:
            return False

    async def _validate_rss(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                response.raise_for_status()
                return "<?xml" in response.text or "<rss" in response.text or "<feed" in response.text
        except Exception:
            return False

    async def _register(self, candidate: dict[str, Any]) -> None:
        """Add candidate as inactive source, avoiding duplicates."""
        url = candidate.get("url", "")
        source_type = candidate.get("type", "website")
        name = candidate.get("name", "Discovered source")

        if source_type == "telegram":
            username = url.replace("https://t.me/", "").strip("/")
            existing = await self.db.execute(
                select(Channel).filter(
                    (Channel.username == username) | (Channel.telegram_id == username)
                )
            )
            if existing.scalar_one_or_none():
                return
            channel = Channel(
                username=username,
                name=name,
                is_active=False,
                description=f"Autodiscovered: {candidate.get('reason', '')}",
            )
            self.db.add(channel)
        else:
            existing = await self.db.execute(
                select(WebsiteSource).filter(WebsiteSource.url == url)
            )
            if existing.scalar_one_or_none():
                return
            source = WebsiteSource(
                name=name,
                url=url,
                site_type=source_type,
                is_active=False,
                extraction_prompt=f"Autodiscovered: {candidate.get('reason', '')}",
            )
            self.db.add(source)

        await self.db.commit()
        logger.info("[SOURCE DISCOVERY] Registered candidate: %s (%s)", name, url)
