"""Async Ollama service with semaphore-based concurrent processing."""

import json
import asyncio
import logging
from typing import Any

from ollama import AsyncClient

from telegram_processor.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def is_ollama_available() -> bool:
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

FIELD RULES:
- If a field is unknown or not mentioned, use null (not "", not "N/A", not "unknown")
- "is_remote": true if remote/wfh/anywhere/居家/远程 mentioned, false if on-site only, null if not mentioned
- "skills": always an array, empty array [] if none found
- "contact": extract @username, email, or URL. If none found, null
- "contact_type": only fill if contact is found, otherwise null
- "confidence": "high" if category is clear, "medium" if somewhat ambiguous, "low" if guessing
- "looking_for_work": true if person is actively seeking work, false if just sharing info, null if unclear

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
    "is_remote": true/false/null,
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
    "looking_for_work": true/false/null,
    "summary": ""
  }
}"""

RECOMMENDED_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class AsyncOllamaAnalyzer:
    def __init__(self, base_url: str = None, model_name: str = None, max_concurrent: int = 3):
        self.client = AsyncClient(host=base_url or OLLAMA_BASE_URL)
        self.model_name = model_name or OLLAMA_MODEL or RECOMMENDED_MODEL
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_message(self, message_text: str) -> dict[str, Any]:
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
                            "num_predict": 2048,
                            "num_ctx": 4096,
                            "low_vram": True,
                            "num_gpu": 50,
                        }
                    ),
                    timeout=600.0
                )

                response_text = response['response']
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    if "```json" in response_text:
                        json_part = response_text.split("```json")[1].split("```")[0]
                        return json.loads(json_part.strip())
                    elif "```" in response_text:
                        json_part = response_text.split("```")[1].split("```")[0]
                        return json.loads(json_part.strip())
                    else:
                        logger.error(f"[Ollama] JSON parse failed, raw: {response_text[:300]}")
                        raise

            except asyncio.TimeoutError:
                logger.error("Ollama request timed out at 110s limit.")
                raise ValueError("Ollama request timed out")
            except json.JSONDecodeError as e:
                logger.error(f"Failed parsing structural JSON from response: {e}")
                raise ValueError(f"JSON parse failed: {e}")
            except Exception as e:
                logger.error(f"Ollama Extraction Pipeline Error: {str(e)}")
                raise


_analyzer_instance: AsyncOllamaAnalyzer = None

def get_analyzer() -> AsyncOllamaAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AsyncOllamaAnalyzer()
    return _analyzer_instance