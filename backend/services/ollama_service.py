"""Async Ollama service with semaphore-based concurrent processing."""

import json
import asyncio
import logging
import re
from typing import Any

from ollama import AsyncClient

from telegram_processor.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def is_ollama_available() -> bool:
    try:
        client = AsyncClient(host=OLLAMA_BASE_URL)
        await asyncio.wait_for(client.list(), timeout=5)
        return True
    except Exception:
        return False


# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
# Condensed for speed — same logic, fewer tokens
SYSTEM_PROMPT = """Telegram message classifier for remote tech job boards. Output: JSON only, no markdown, no explanation.

CATEGORIES:
- "job_posting": Software engineering role offer (frontend, backend, fullstack, devops, mobile, blockchain, smart_contract, qa, data, ml_ai, security, systems, embedded)
- "personal_info": Software developer (coder/programmer) describing themselves or seeking work. MUST have software engineering skills or experience.
- "other": Non-engineering (design, marketing, HR, sales, product, ops, finance, trading, support, admin, etc.) OR job seekers without software engineering background

RULES:
- "translated_text": Full English translation of the original message. Required for ALL categories including other. If the message is not in English, translate the FULL message to English and put it in "translated_text". If the message is already in English, copy the original text into "translated_text". Never return null for "translated_text"
- "skills": array of individual items, never comma-separated in one string
- Unknown fields: null (not "", not "N/A")
- "is_remote": true=remote/wfh/anywhere mentioned; false=onsite only; null=not mentioned
- "contacts": array of {type, value} for ALL contact methods found; null if none
- "confidence": high/medium/low
- "looking_for_work": true=actively seeking; false=just sharing; null=unclear

CONTACT TYPES: telegram(@user or t.me/), email, linkedin, twitter, discord, wechat(微信), whatsapp, line, github, website, other

OUTPUT: Only return the block matching the category.

job_posting:
{"category":"job_posting","confidence":"...","translated_text":"<REQUIRED: full English translation>","job_posting":{"title":null,"company":null,"company_link":null,"location":null,"is_remote":null,"role_type":"frontend|backend|fullstack|devops|mobile|blockchain|smart_contract|data|ml_ai|qa|security|systems|embedded|other_tech","skills":[],"contacts":[{"type":"...","value":"..."}],"summary":null}}

personal_info:
{"category":"personal_info","confidence":"...","translated_text":"<REQUIRED: full English translation>","personal_info":{"name":null,"skills":[],"experience":null,"portfolio":null,"github":null,"linkedin":null,"contacts":[{"type":"...","value":"..."}],"looking_for_work":null,"summary":null}}

other:
{"category":"other","confidence":"...","translated_text":"<REQUIRED: full English translation>"}"""


# ── PRE-FILTER ────────────────────────────────────────────────────────────────
# Only block obvious spam — let Ollama handle all other classification

_SPAM_PATTERN = re.compile(
    r"airdrop|casino|gambling|betting|forex|trading.signal|dropshipping|\bmlm\b|"
    r"赌博|博彩|外汇|微商",
    re.IGNORECASE,
)

def should_analyze_message(text: str) -> bool:
    """Return False only for obvious spam. Everything else goes to Ollama."""
    if not text or len(text.strip()) < 10:
        return False
    if _SPAM_PATTERN.search(text):
        return False
    return True


# ── ANALYZER ─────────────────────────────────────────────────────────────────

RECOMMENDED_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class AsyncOllamaAnalyzer:
    def __init__(self, base_url: str = None, model_name: str = None, max_concurrent: int = 3):
        self.client = AsyncClient(host=base_url or OLLAMA_BASE_URL)
        self.model_name = model_name or OLLAMA_MODEL or RECOMMENDED_MODEL
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_message(self, message_text: str) -> dict[str, Any]:
        import time
        if not should_analyze_message(message_text):
            return {
                "category": "other",
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }

        # Trim to 2000 chars, collapse whitespace
        clean_text = " ".join(message_text.split())[:2000]
        msg_preview = clean_text[:50]

        # Track semaphore wait time
        wait_start = time.time()
        logger.info(f"[OLLAMA] Waiting for semaphore | Msg: {msg_preview}... | Semaphore: {self.semaphore._value if hasattr(self.semaphore, '_value') else 'N/A'}")
        
        async with self.semaphore:
            wait_elapsed = time.time() - wait_start
            logger.info(f"[OLLAMA] Acquired semaphore | Msg: {msg_preview}... | Wait time: {wait_elapsed:.1f}s")
            try:
                response = await asyncio.wait_for(
                    self.client.generate(
                        model=self.model_name,
                        system=SYSTEM_PROMPT,
                        prompt=clean_text,
                        format="json",
                        options={
                            "temperature": 0.0,
                            "num_predict": 2048,   # 800 max observed + 25% margin
                            "num_ctx": 2048,
                            "num_gpu": 99,         # 7B fits fully in 6GB VRAM
                            "keep_alive": -1,      # keep model loaded
                        },
                    ),
                    timeout=120.0,  # 7B @ ~15 tok/s: 2048 tokens ≈ 136s + margin
                )

                response_text = response["response"]

                usage = {
                    "input_tokens": response.get("prompt_eval_count", 0),
                    "output_tokens": response.get("eval_count", 0),
                    "total_tokens": (
                        response.get("prompt_eval_count", 0)
                        + response.get("eval_count", 0)
                    ),
                    "prompt_eval_duration": response.get("prompt_eval_duration", 0),
                    "eval_duration": response.get("eval_duration", 0),
                    "total_duration": response.get("total_duration", 0),
                }

                # Warn if output was truncated
                if usage["output_tokens"] >= 1024:
                    logger.warning(
                        f"[Ollama] Output may be truncated: {usage['output_tokens']} tokens"
                    )

                result = self._parse_json(response_text)
                result["usage"] = usage
                total_elapsed = time.time() - wait_start
                logger.info(f"[OLLAMA] Success | Msg: {msg_preview}... | Category: {result.get('category', 'unknown')} | Total time: {total_elapsed:.1f}s | Tokens: {usage['total_tokens']}")
                return result

            except asyncio.TimeoutError:
                elapsed = time.time() - wait_start
                logger.error(f"[OLLAMA] TIMEOUT | Msg: {msg_preview}... | Total time: {elapsed:.1f}s")
                raise ValueError("Ollama request timed out after 120s")
            except json.JSONDecodeError as e:
                elapsed = time.time() - wait_start
                logger.error(f"[OLLAMA] JSON ERROR | Msg: {msg_preview}... | Time: {elapsed:.1f}s | Error: {e}")
                raise ValueError(f"JSON parse failed: {e}")
            except Exception as e:
                elapsed = time.time() - wait_start
                logger.error(f"[OLLAMA] ERROR | Msg: {msg_preview}... | Time: {elapsed:.1f}s | Error: {e}")
                raise

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON, stripping markdown fences if present."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip ```json ... ``` or ``` ... ```
        for pattern in (r"```json\s*(.*?)```", r"```\s*(.*?)```"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())

        raise json.JSONDecodeError("No valid JSON found", text, 0)


# ── SINGLETON ─────────────────────────────────────────────────────────────────

_analyzer_instance: AsyncOllamaAnalyzer = None


def get_analyzer() -> AsyncOllamaAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AsyncOllamaAnalyzer()
    return _analyzer_instance