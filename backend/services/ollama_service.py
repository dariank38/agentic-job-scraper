"""Async Ollama service with semaphore-based concurrent processing."""

import json
import asyncio
import logging
import re
import time
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
SYSTEM_PROMPT = """你是电报消息分类器。仅输出JSON，无markdown。

分类：
- job_posting：公司招聘工程师（前端/后端/全栈/运维/移动/区块链/QA/数据/AI）
- personal_info：开发者求职（必须含技术栈/框架/经验年限/作品集/GitHub等具体技术信息）
- other：非技术内容或仅含联系方式的闲聊

字段规则：
- skills：数组，非逗号字符串
- is_remote：true=远程，false=现场，null=未提及
- contacts：[{type,value}]，type可为telegram/email/linkedin/github/wechat/whatsapp/website/other
- confidence：high/medium/low
- 未知字段：null

job_posting输出：
{"category":"job_posting","confidence":"...","translated_text":"...","job_posting":{"company":null,"company_link":null,"location":null,"is_remote":null,"role_type":"frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech","skills":[],"contacts":[],"summary":null}}

personal_info输出：
{"category":"personal_info","confidence":"...","translated_text":"...","personal_info":{"name":null,"skills":[],"experience":null,"portfolio":null,"github":null,"linkedin":null,"contacts":[],"looking_for_work":null,"summary":null}}

other输出：
{"category":"other","confidence":"..."}"""


# ── PRE-FILTER ────────────────────────────────────────────────────────────────
_SPAM_PATTERN = re.compile(
    r"airdrop|casino|gambling|betting|forex|trading.signal|dropshipping|\bmlm\b|"
    r"赌博|博彩|外汇|微商",
    re.IGNORECASE,
)

# 50 char threshold is too aggressive — could filter short job messages
# Focus on spam pattern matching and relax length filter
_MIN_LENGTH = 20

def should_analyze_message(text: str) -> bool:
    """Return False for spam or very short messages."""
    if not text or len(text.strip()) < _MIN_LENGTH:
        return False
    if _SPAM_PATTERN.search(text):
        return False
    return True


# ── ANALYZER ─────────────────────────────────────────────────────────────────

RECOMMENDED_MODEL = "qwen2.5:14b"

# Single source of truth for config: config → constant → default fallback
_DEFAULT_MODEL = OLLAMA_MODEL or RECOMMENDED_MODEL


class AsyncOllamaAnalyzer:
    def __init__(
        self,
        base_url: str = None,
        model_name: str = None,
        max_concurrent: int = 1,
    ):
        self.client = AsyncClient(host=base_url or OLLAMA_BASE_URL)
        self.model_name = model_name or _DEFAULT_MODEL
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # Track pending jobs directly (avoid using private _value attribute)
        self._pending: int = 0

    def _get_model_options(self, message_length: int) -> dict:
        """Calculate num_ctx and num_predict dynamically based on message length + system prompt."""
        # System prompt adds to context window
        system_prompt_length = len(SYSTEM_PROMPT)
        total_input_length = message_length + system_prompt_length

        if total_input_length < 512:
            num_ctx, num_predict = 1024, 512
        elif total_input_length < 1024:
            num_ctx, num_predict = 2048, 1024
        elif total_input_length < 2048:
            num_ctx, num_predict = 4096, 2048
        else:
            num_ctx, num_predict = 8192, 4096

        logger.info(
            "[OLLAMA] Message: %d chars | System prompt: %d chars | Total: %d chars | num_ctx: %d | num_predict: %d",
            message_length, system_prompt_length, total_input_length, num_ctx, num_predict,
        )

        return {
            "temperature": 0.0,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "keep_alive": -1,
        }

    async def analyze_message(self, message_text: str) -> dict[str, Any]:
        if not should_analyze_message(message_text):
            return {
                "category": "other",
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }

        # Normalize whitespace and limit to 2000 chars
        clean_text = " ".join(message_text.split())[:2000]
        msg_preview = clean_text[:50]

        # Compute options before acquiring semaphore (pure computation)
        options = self._get_model_options(len(clean_text))

        self._pending += 1
        wait_start = time.monotonic()
        logger.info(
            "[OLLAMA] Waiting for semaphore | pending: %d | msg: %.50s...",
            self._pending, clean_text,
        )

        async with self.semaphore:
            self._pending -= 1
            wait_elapsed = time.monotonic() - wait_start
            process_start = time.monotonic()
            logger.info(
                "[OLLAMA] Semaphore acquired | wait: %.1fs | msg: %.50s...",
                wait_elapsed, clean_text,
            )

            try:
                response = await asyncio.wait_for(
                    self.client.generate(
                        model=self.model_name,
                        system=SYSTEM_PROMPT,
                        prompt=clean_text,
                        format="json",
                        options=options,
                    ),
                    timeout=300.0,
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

                if usage["output_tokens"] >= 1024:
                    logger.warning(
                        "[OLLAMA] Output may be truncated: %d tokens",
                        usage["output_tokens"],
                    )

                result = self._parse_json(response_text)
                result["usage"] = usage

                process_elapsed = time.monotonic() - process_start
                logger.info(
                    "[OLLAMA] Success | msg: %.50s... | category: %s | wait: %.1fs | process: %.1fs | tokens in/out: %d/%d",
                    clean_text,
                    result.get("category", "unknown"),
                    wait_elapsed,
                    process_elapsed,
                    usage["input_tokens"],
                    usage["output_tokens"],
                )
                return result

            except asyncio.TimeoutError:
                elapsed = time.monotonic() - process_start
                logger.error(
                    "[OLLAMA] TIMEOUT | msg: %.50s... | process time: %.1fs",
                    msg_preview, elapsed,
                )
                raise ValueError("Ollama request timed out after 300s")

            except json.JSONDecodeError as e:
                elapsed = time.monotonic() - process_start
                logger.error(
                    "[OLLAMA] JSON ERROR | msg: %.50s... | time: %.1fs | error: %s",
                    msg_preview, elapsed, e,
                )
                raise ValueError(f"JSON parse failed: {e}")

            except Exception as e:
                elapsed = time.monotonic() - process_start
                logger.error(
                    "[OLLAMA] ERROR | msg: %.50s... | time: %.1fs | error: %s",
                    msg_preview, elapsed, e,
                )
                raise

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON, stripping markdown fences if present."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        for pattern in (r"```json\s*(.*?)```", r"```\s*(.*?)```"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())

        raise json.JSONDecodeError("No valid JSON found", text, 0)


analyzer = AsyncOllamaAnalyzer()


def get_analyzer() -> AsyncOllamaAnalyzer:
    """Kept for backward compatibility."""
    return analyzer