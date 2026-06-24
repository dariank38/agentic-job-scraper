"""RSS extractor with structured JSON output and chunking. Supports Ollama and NVIDIA providers."""

import json
import logging
import os
from typing import Optional, List
from ollama import AsyncClient
import httpx

from web_crawler.models import ExtractedData, JobPosting, DeveloperInfo, ContactInfo
from web_crawler.prompts import get_prompt_for_site

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# NVIDIA configuration
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "qwen/qwen3.5-397b-a17b")

MAX_CHARS = 3000  # Safe chunk size (~1000-1500 tokens)


class Extractor:
    """RSS extractor using Ollama or NVIDIA with structured JSON output."""

    def __init__(self, model: str = None, base_url: str = None):
        if model:
            self.model = model
        else:
            try:
                from app.routes.settings import get_ollama_model
                self.model = get_ollama_model()
            except Exception:
                self.model = OLLAMA_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL
        self.client = AsyncClient(host=self.base_url)

    def _get_provider(self) -> str:
        try:
            from app.routes.settings import get_analyze_provider
            return get_analyze_provider()
        except Exception:
            return "ollama"

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
        provider = self._get_provider()
        for i, chunk in enumerate(chunks):
            logger.info(f"[EXTRACTOR] Chunk {i + 1}/{len(chunks)} — sending {len(chunk)} chars to {provider.upper()}")
            if provider == "nvidia":
                result, usage = await self._call_llm_nvidia(chunk, prompt_template)
            else:
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

    async def _call_llm_nvidia(self, content: str, prompt_template: str) -> tuple[Optional[dict], dict]:
        """Call NVIDIA NIM API for extraction."""
        prompt = prompt_template.format(content=content)
        # Scale output budget with input size: extraction JSON can be large for multi-job content
        content_len = len(content)
        if content_len < 1000:
            max_tokens = 1024
        elif content_len < 2000:
            max_tokens = 2048
        else:
            max_tokens = 4096
        payload = {
            "model": NVIDIA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(NVIDIA_INVOKE_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            raw = data["choices"][0]["message"]["content"].strip()
            usage_data = data.get("usage", {})
            usage = {
                "input_tokens": usage_data.get("prompt_tokens", 0),
                "output_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }
            logger.info(f"[EXTRACTOR] NVIDIA response ({len(raw)} chars) | max_tokens={max_tokens} | tokens: in={usage['input_tokens']} out={usage['output_tokens']}")
            logger.info(f"[EXTRACTOR] Raw preview: {raw[:300]!r}{'...' if len(raw) > 300 else ''}")
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            jobs_count = len(parsed.get("job_postings", []))
            logger.info(f"[EXTRACTOR] Parsed OK — job_postings={jobs_count}")
            return parsed, usage
        except json.JSONDecodeError as e:
            logger.error(f"[EXTRACTOR] NVIDIA JSON parse error: {e} | raw={raw[:200]!r}")
            return None, {}
        except Exception as e:
            logger.error(f"[EXTRACTOR] NVIDIA LLM error: {e}")
            return None, {}

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
                    # Normalize fields: convert list requirements to string
                    job_data = {k: v for k, v in j.items() if v}
                    if isinstance(job_data.get("requirements"), list):
                        job_data["requirements"] = "; ".join(job_data["requirements"])
                    if isinstance(job_data.get("location"), list):
                        job_data["location"] = ", ".join(job_data["location"])
                    # Normalize salary: convert dict to string
                    if isinstance(job_data.get("salary"), dict):
                        salary_dict = job_data["salary"]
                        min_salary = salary_dict.get("min")
                        max_salary = salary_dict.get("max")
                        if min_salary and max_salary:
                            job_data["salary"] = f"{min_salary}-{max_salary}"
                        elif min_salary:
                            job_data["salary"] = str(min_salary)
                        elif max_salary:
                            job_data["salary"] = str(max_salary)
                    # Normalize role_type: convert comma-separated to pipe-separated for consistent tag display
                    if isinstance(job_data.get("role_type"), str) and "," in job_data["role_type"]:
                        job_data["role_type"] = job_data["role_type"].replace(", ", "|").replace(",", "|")
                    jobs.append(JobPosting(**job_data))

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
            # Deduplicate and normalize social links (convert dicts to strings)
            socials_dedup = []
            seen = set()
            for s in socials:
                # Convert dict to formatted string
                if isinstance(s, dict):
                    s_str = f"{s.get('type', 'link')}: {s.get('value', '')}".strip()
                else:
                    s_str = str(s)
                if s_str not in seen:
                    seen.add(s_str)
                    socials_dedup.append(s_str)

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
