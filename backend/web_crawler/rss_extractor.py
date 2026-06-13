"""RSS Ollama extractor with structured JSON output and chunking."""

import json
import logging
import os
from typing import Optional, List
from ollama import AsyncClient

from web_crawler.models import ExtractedData, JobPosting, DeveloperInfo, ContactInfo
from web_crawler.prompts import get_prompt_for_site

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

MAX_CHARS = 3000  # Safe chunk size for Ollama (~1000-1500 tokens)


class Extractor:
    """RSS extractor using Ollama with structured JSON output."""

    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or OLLAMA_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL
        self.client = AsyncClient(host=self.base_url)

    async def extract(self, content: str, source_url: str, custom_prompt: str = None, site_type: str = None) -> tuple[ExtractedData, dict]:
        """Extract structured data from RSS content using Ollama.

        Args:
            content: Text content to analyze.
            source_url: Original URL of the content.
            custom_prompt: Optional custom prompt override.

        Returns:
            Tuple of (ExtractedData with job postings/developer info/contact info, usage dict with token stats).
        """
        logger.info(f"[EXTRACTOR] ▶ START | source={source_url} | content_len={len(content)} chars | model={self.model}")

        # Get appropriate prompt for extraction
        prompt_template = get_prompt_for_site(site_type=site_type, custom_prompt=custom_prompt)

        # Chunk if too long
        chunks = self._chunk(content)
        logger.info(f"[EXTRACTOR] Split into {len(chunks)} chunk(s) (MAX_CHARS={MAX_CHARS})")

        all_results = []
        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for i, chunk in enumerate(chunks):
            logger.info(f"[EXTRACTOR] Chunk {i + 1}/{len(chunks)} — sending {len(chunk)} chars to Ollama")
            result, usage = await self._call_llm(chunk, prompt_template)
            if result:
                all_results.append(result)
            if usage:
                total_usage["input_tokens"] += usage.get("input_tokens", 0)
                total_usage["output_tokens"] += usage.get("output_tokens", 0)
                total_usage["total_tokens"] += usage.get("total_tokens", 0)

        merged = self._merge_results(all_results, source_url)
        logger.info(f"[EXTRACTOR] ✓ DONE | jobs={len(merged.job_postings)} | devs={1 if merged.developer_info else 0} | emails={len(merged.contact_info.emails) if merged.contact_info else 0} | tokens: in={total_usage['input_tokens']} out={total_usage['output_tokens']} total={total_usage['total_tokens']}")
        return merged, total_usage

    async def _call_llm(self, content: str, prompt_template: str) -> tuple[Optional[dict], dict]:
        """Call Ollama LLM for extraction.

        Args:
            content: Text chunk to analyze.
            prompt_template: The prompt template to use.

        Returns:
            Tuple of (parsed JSON dict if successful else None, usage dict with token stats).
        """
        prompt = prompt_template.format(content=content)
        try:
            response = await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}  # Low temp for factual extraction
            )
            raw = response["message"]["content"].strip()
            usage = {
                "input_tokens": response.get("prompt_eval_count", 0),
                "output_tokens": response.get("eval_count", 0),
                "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
            }
            logger.info(f"[EXTRACTOR] Ollama response ({len(raw)} chars) | tokens: in={usage['input_tokens']} out={usage['output_tokens']} total={usage['total_tokens']}")
            logger.info(f"[EXTRACTOR] Raw preview: {raw[:300]!r}{'...' if len(raw) > 300 else ''}")

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw)
            jobs_count = len(parsed.get("job_postings", []))
            logger.info(f"[EXTRACTOR] Parsed OK — job_postings={jobs_count}")
            return parsed, usage
        except json.JSONDecodeError as e:
            logger.error(f"[EXTRACTOR] JSON parse error: {e} | raw={raw[:200]!r}")
            return None, {}
        except Exception as e:
            logger.error(f"[EXTRACTOR] LLM error: {e}")
            return None, {}

    def _chunk(self, text: str) -> List[str]:
        """Split text into chunks for processing.

        Args:
            text: Text to chunk.

        Returns:
            List of text chunks.
        """
        return [text[i:i + MAX_CHARS] for i in range(0, len(text), MAX_CHARS)]

    def _merge_results(self, results: List[dict], source_url: str) -> ExtractedData:
        """Merge results from multiple chunks.

        Args:
            results: List of extraction results from chunks.
            source_url: Original URL.

        Returns:
            Merged ExtractedData.
        """
        jobs, tech_stack, oss_links = [], [], []
        emails, phones, socials, persons = [], [], [], []
        team_name = None
        dev_description = None

        for r in results:
            for j in r.get("job_postings", []):
                # Add job posting even if title is missing - backend will apply fallback
                if j.get("title") or j.get("summary") or j.get("company") or j.get("role_type"):
                    jobs.append(JobPosting(**{k: v for k, v in j.items() if v}))

            dev = r.get("developer_info", {})
            if dev:
                team_name = team_name or dev.get("team_name")
                dev_description = dev_description or dev.get("description")
                tech_stack += dev.get("tech_stack", [])
                oss_links += dev.get("open_source_links", [])

            contact = r.get("contact_info", {})
            if contact:
                emails += contact.get("emails", [])
                phones += contact.get("phone_numbers", [])
                socials += contact.get("social_links", [])
                persons += contact.get("contact_persons", [])

        developer_info = None
        if team_name or tech_stack or oss_links:
            developer_info = DeveloperInfo(
                team_name=team_name,
                tech_stack=list(set(tech_stack)),
                open_source_links=list(set(oss_links)),
                description=dev_description
            )

        contact_info = None
        if emails or phones or socials or persons:
            # Deduplicate social links (dicts) by converting to tuples
            socials_dedup = []
            seen = set()
            for s in socials:
                # Convert dict to tuple of sorted items for deduplication
                s_tuple = tuple(sorted(s.items())) if isinstance(s, dict) else s
                if s_tuple not in seen:
                    seen.add(s_tuple)
                    socials_dedup.append(s)

            contact_info = ContactInfo(
                emails=list(set(emails)),
                phone_numbers=list(set(phones)),
                social_links=socials_dedup,
                contact_persons=list(set(persons))
            )

        return ExtractedData(
            source_url=source_url,
            job_postings=jobs,
            developer_info=developer_info,
            contact_info=contact_info
        )
