"""Smart Ollama extractor with structured JSON output and chunking."""

import json
import logging
from typing import Optional, List
from ollama import chat

from web_crawler.models import ExtractedData, JobPosting, DeveloperInfo, ContactInfo

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
You are an expert web content analyzer for job postings and developer information.
Extract the following from the text below and return ONLY a valid JSON object.
No explanation, no markdown, no extra text.

JSON Schema:
{{
  "job_postings": [
    {{
      "title": "string",
      "requirements": "string or null",
      "deadline": "string or null",
      "url": "string or null",
      "company": "string or null",
      "location": "string or null",
      "is_remote": "boolean or null",
      "salary": "string or null"
    }}
  ],
  "developer_info": {{
    "team_name": "string or null",
    "tech_stack": ["list of technologies"],
    "open_source_links": ["list of github or repo urls"],
    "description": "string or null"
  }},
  "contact_info": {{
    "emails": ["list of emails"],
    "phone_numbers": ["list of phone numbers"],
    "social_links": ["list of social media urls"],
    "contact_persons": ["list of person names"]
  }}
}}

Text to analyze:
{content}
"""

MAX_CHARS = 6000  # qwen2.5:7b context limit buffer


class SmartOllamaExtractor:
    """Smart extractor using Ollama with structured JSON output."""

    def __init__(self, model: str = "qwen2.5:7b"):
        self.model = model

    def extract(self, content: str, source_url: str) -> ExtractedData:
        """Extract structured data from content using Ollama.

        Args:
            content: Text content to analyze.
            source_url: Original URL of the content.

        Returns:
            ExtractedData with job postings, developer info, and contact info.
        """
        logger.info(f"[EXTRACTOR] Processing {len(content)} chars from {source_url}")

        # Chunk if too long
        chunks = self._chunk(content)
        logger.info(f"[EXTRACTOR] Split into {len(chunks)} chunks")

        all_results = []
        for i, chunk in enumerate(chunks):
            logger.info(f"[EXTRACTOR] Processing chunk {i + 1}/{len(chunks)}")
            result = self._call_llm(chunk)
            if result:
                all_results.append(result)

        merged = self._merge_results(all_results, source_url)
        logger.info(f"[EXTRACTOR] Extracted {len(merged.job_postings)} jobs, {len(merged.contact_info.emails) if merged.contact_info else 0} emails")
        return merged

    def _call_llm(self, content: str) -> Optional[dict]:
        """Call Ollama LLM for extraction.

        Args:
            content: Text chunk to analyze.

        Returns:
            Parsed JSON dict if successful, None otherwise.
        """
        prompt = PROMPT_TEMPLATE.format(content=content)
        try:
            response = chat(
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
