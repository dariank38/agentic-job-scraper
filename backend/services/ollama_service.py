"""Async Ollama service with semaphore-based concurrent processing."""

import json
import asyncio
import logging
from typing import Any

from ollama import AsyncClient

from telegram_processor.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def is_ollama_available() -> bool:
    """Check if Ollama server is accessible.

    Returns:
        True if Ollama is running and accessible, False otherwise.
    """
    try:
        client = AsyncClient(host=OLLAMA_BASE_URL)
        await client.list()
        return True
    except Exception:
        return False


SYSTEM_PROMPT = """You are a Telegram message analyzer for tech job boards. Analyze the message and categorize it. The message may be in any language — always respond in English JSON only.

CATEGORIES:
1. "job_posting" - Software development/engineering job posting ONLY (frontend, backend, fullstack, devops, mobile, blockchain, smart_contract, QA, data engineer, ML/AI engineer, etc.)
2. "personal_info" - Personal information of software developers/engineers (skills, experience, portfolio, looking for work, etc.)
3. "other" - Everything else

RULES:
- ALWAYS translate the message to English in the "translated_text" field
- For job_posting: Extract job details (title, company, location, remote status, role type, skills, contact)
- For personal_info: Extract developer details (name, skills, experience, portfolio, github, linkedin, contact, looking_for_work)
- SKIP as "other" if: ANY non-software development role including: design (UI/UX, graphic), marketing, sales, HR, product management, community management, content writing, accounting, customer support, business development, operations, data entry, translation, virtual assistant, etc.
- ONLY include pure software development/engineering roles: frontend, backend, fullstack, devops, mobile, blockchain, smart_contract, QA, data engineer, ML/AI engineer, security, systems programming, embedded systems
- For skills: Split long skill strings into individual skills. Example: "DeFi protocols (prediction markets, perpetual contracts DEX, cross-chain aggregation trading engine, lending, staking/re-staking)" should become ["DeFi protocols", "prediction markets", "perpetual contracts DEX", "cross-chain aggregation trading engine", "lending", "staking", "re-staking"]

Return ONLY a raw JSON object. No markdown, no explanation, no code blocks. Exact format:
{
  "category": "job_posting | personal_info | other",
  "confidence": "high | medium | low",
  "translated_text": "Full English translation of the original message",
  "job_posting": {
    "title": "",
    "company": "",
    "company_link": "",
    "location": "",
    "is_remote": true/false,
    "role_type": "frontend | backend | fullstack | devops | mobile | blockchain | smart_contract | data | ml_ai | qa | security | systems | embedded | other_tech",
    "skills": ["skill1", "skill2"],
    "contact": "",
    "contact_type": "telegram | email | linkedin | twitter | discord | other",
    "summary": ""
  },
  "personal_info": {
    "name": "",
    "skills": ["skill1", "skill2"],
    "experience": "",
    "portfolio": "",
    "github": "",
    "linkedin": "",
    "contact": "",
    "contact_type": "telegram | email | linkedin | twitter | discord | other",
    "summary": ""
  }
}"""

RECOMMENDED_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class AsyncOllamaAnalyzer:
    """Async Ollama analyzer with semaphore-based concurrency control.
    """

    def __init__(self, base_url: str = None, model_name: str = None, max_concurrent: int = 3):
        """
        Initializes the async parser.

        Args:
            base_url: Ollama server URL (defaults to config)
            model_name: Ollama model name (defaults to RECOMMENDED_MODEL)
            max_concurrent: Max concurrent requests (3 for hybrid GPU/CPU processing)
        """
        self.client = AsyncClient(host=base_url or OLLAMA_BASE_URL)
        self.model_name = model_name or OLLAMA_MODEL or RECOMMENDED_MODEL
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_message(self, message_text: str) -> dict[str, Any]:
        """
        Sends a single message to Ollama concurrently using a semaphore constraint.

        Args:
            message_text: The message text to analyze

        Returns:
            Parsed JSON result or error dict with category="other"
        """
        if not message_text or len(message_text.strip()) < 10:
            return {"category": "other"}

        clean_text = " ".join(message_text.split())[:2000]

        async with self.semaphore:
            try:
                response = await asyncio.wait_for(
                    self.client.generate(
                        model=self.model_name,
                        system=SYSTEM_PROMPT,
                        prompt=clean_text,
                        format="json",
                        options={
                            "temperature": 0.0,
                            "num_predict": 2048,   # Allow full JSON with translated_text
                            "num_ctx": 4096,       # Sufficient context for prompt + input
                            "low_vram": True,      # Offload to CPU/RAM when needed
                            "num_gpu": 50,         # 50% layers on GPU, 50% on RAM (hybrid)
                        }
                    ),
                    timeout=600.0
                )

                response_text = response['response']
                try:
                    result = json.loads(response_text)
                    return result
                except json.JSONDecodeError:
                    if "```json" in response_text:
                        json_part = response_text.split("```json")[1].split("```")[0]
                        result = json.loads(json_part.strip())
                        return result
                    elif "```" in response_text:
                        json_part = response_text.split("```")[1].split("```")[0]
                        result = json.loads(json_part.strip())
                        return result
                    else:
                        logger.error(f"[Ollama] JSON parse failed, raw: {response_text[:300]}")
                        raise

            except asyncio.TimeoutError:
                logger.error("Ollama request timed out at 60s limit.")
                raise ValueError("Ollama request timed out")
            except json.JSONDecodeError as e:
                logger.error(f"Failed parsing structural JSON from response: {e}")
                raise ValueError(f"JSON parse failed: {e}")
            except Exception as e:
                logger.error(f"Ollama Extraction Pipeline Error: {str(e)}")
                raise


_analyzer_instance: AsyncOllamaAnalyzer = None

def get_analyzer() -> AsyncOllamaAnalyzer:
    """Get or create the global analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AsyncOllamaAnalyzer()
    return _analyzer_instance