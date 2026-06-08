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


SYSTEM_PROMPT = """You are a Telegram message classifier for tech job boards. Always respond in English JSON only. No markdown, no code blocks, no explanation.

CATEGORIES:
- "job_posting": Offering a software engineering role (frontend, backend, fullstack, devops, mobile, blockchain, smart_contract, qa, data, ml_ai, security, systems, embedded)
- "personal_info": A software developer describing themselves, skills, or seeking work
- "other": Anything non-engineering — design, marketing, HR, sales, product, content, ops, finance, support, recruiting, admin, translation, data entry, VA, community management

RULES:
- Translate the full message to English in "translated_text"
- Split ALL skills into individual array items — never comma-separated strings in one item
- Unknown/unmentioned fields: null (not "", not "N/A")
- "is_remote": true/false/null — true only if remote/wfh/anywhere explicitly mentioned
- "contacts": array of all contact methods found — null if none found
- "confidence": high/medium/low
- "looking_for_work": true if actively seeking, false if just sharing info, null if unclear

CONTACT TYPE DETECTION:
- "telegram": starts with @ or t.me/
- "email": contains @domain.tld
- "linkedin": linkedin.com URL or "LinkedIn: name"
- "twitter": twitter.com, x.com, or @handle labeled as Twitter/X
- "discord": discord.gg/ or username#1234 or labeled as Discord
- "wechat": labeled as WeChat, 微信, or starts with wechat ID
- "whatsapp": labeled as WhatsApp or wa.me/
- "line": labeled as LINE or line.me/
- "github": github.com URL
- "website": any other URL
- "other": any other labeled contact method

OUTPUT: Return only the relevant block for the detected category.

job_posting →
{
  "category": "job_posting",
  "confidence": "high | medium | low",
  "translated_text": "...",
  "job_posting": {
    "title": null,
    "company": null,
    "company_link": null,
    "location": null,
    "is_remote": null,
    "role_type": "frontend | backend | fullstack | devops | mobile | blockchain | smart_contract | data | ml_ai | qa | security | systems | embedded | other_tech",
    "skills": [],
    "contacts": [
      {"type": "telegram | email | linkedin | twitter | discord | wechat | whatsapp | line | github | website | other", "value": "..."}
    ],
    "summary": null
  }
}

personal_info →
{
  "category": "personal_info",
  "confidence": "high | medium | low",
  "translated_text": "...",
  "personal_info": {
    "name": null,
    "skills": [],
    "experience": null,
    "portfolio": null,
    "github": null,
    "linkedin": null,
    "contacts": [
      {"type": "telegram | email | linkedin | twitter | discord | wechat | whatsapp | line | github | website | other", "value": "..."}
    ],
    "looking_for_work": null,
    "summary": null
  }
}

other →
{
  "category": "other",
  "confidence": "high | medium | low",
  "translated_text": "..."
}"""

RECOMMENDED_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class AsyncOllamaAnalyzer:
    def __init__(self, base_url: str = None, model_name: str = None, max_concurrent: int = 3):
        self.client = AsyncClient(host=base_url or OLLAMA_BASE_URL)
        self.model_name = model_name or OLLAMA_MODEL or RECOMMENDED_MODEL
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_message(self, message_text: str) -> dict[str, Any]:
        if not message_text or len(message_text.strip()) < 10:
            return {"category": "other", "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

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
                            "num_ctx": 2048,
                            "low_vram": True,
                            "num_gpu": 99,
                            "keep_alive": -1
                        }
                    ),
                    timeout=600.0
                )

                response_text = response['response']

                # Extract token usage from Ollama response
                usage = {
                    "input_tokens": response.get('prompt_eval_count', 0),
                    "output_tokens": response.get('eval_count', 0),
                    "total_tokens": (response.get('prompt_eval_count', 0) + response.get('eval_count', 0)),
                    "prompt_eval_duration": response.get('prompt_eval_duration', 0),
                    "eval_duration": response.get('eval_duration', 0),
                    "total_duration": response.get('total_duration', 0),
                }

                try:
                    result = json.loads(response_text)
                    result['usage'] = usage
                    return result
                except json.JSONDecodeError:
                    if "```json" in response_text:
                        json_part = response_text.split("```json")[1].split("```")[0]
                        result = json.loads(json_part.strip())
                        result['usage'] = usage
                        return result
                    elif "```" in response_text:
                        json_part = response_text.split("```")[1].split("```")[0]
                        result = json.loads(json_part.strip())
                        result['usage'] = usage
                        return result
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