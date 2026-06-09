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

MAX_CHARS = 6000  # qwen2.5:7b context limit buffer


class Extractor:
    """RSS extractor using Ollama with structured JSON output."""

    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or OLLAMA_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL
        self.client = AsyncClient(host=self.base_url)

    async def extract(self, content: str, source_url: str, custom_prompt: str = None) -> ExtractedData:
        """Extract structured data from RSS content using Ollama.

        Args:
            content: Text content to analyze.
            source_url: Original URL of the content.
            custom_prompt: Optional custom prompt override.

        Returns:
            ExtractedData with job postings, developer info, and contact info.
        """
        logger.info(f"[EXTRACTOR] Processing {len(content)} chars from {source_url}")

        # Get appropriate prompt for extraction
        prompt_template = get_prompt_for_site(custom_prompt=custom_prompt)

        # Chunk if too long
        chunks = self._chunk(content)
        logger.info(f"[EXTRACTOR] Split into {len(chunks)} chunks")

        all_results = []
        for i, chunk in enumerate(chunks):
            logger.info(f"[EXTRACTOR] Processing chunk {i + 1}/{len(chunks)}")
            result = await self._call_llm(chunk, prompt_template)
            if result:
                all_results.append(result)

        merged = self._merge_results(all_results, source_url)
        logger.info(f"[EXTRACTOR] Extracted {len(merged.job_postings)} jobs, {len(merged.contact_info.emails) if merged.contact_info else 0} emails")
        return merged

    async def _call_llm(self, content: str, prompt_template: str) -> Optional[dict]:
        """Call Ollama LLM for extraction.

        Args:
            content: Text chunk to analyze.
            prompt_template: The prompt template to use.

        Returns:
            Parsed JSON dict if successful, None otherwise.
        """
        prompt = prompt_template.format(content=content)
        try:
            response = await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}  # Low temp for factual extraction
            )
            raw = response["message"]["content"].strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            return json.loads(raw)
        except Exception as e:
            logger.error(f"[EXTRACTOR] LLM error: {e}")
            return None

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
                # Only add non-empty job postings
                if j.get("title"):
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
            contact_info = ContactInfo(
                emails=list(set(emails)),
                phone_numbers=list(set(phones)),
                social_links=list(set(socials)),
                contact_persons=list(set(persons))
            )

        return ExtractedData(
            source_url=source_url,
            job_postings=jobs,
            developer_info=developer_info,
            contact_info=contact_info
        )
