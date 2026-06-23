"""Async Ollama service with semaphore-based concurrent processing."""

import json
import asyncio
import logging
import re
import time
from typing import Any
from enum import Enum

from ollama import AsyncClient

from telegram_processor.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class Language(Enum):
    ENGLISH = "english"
    CHINESE = "chinese"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def detect_language(text: str) -> Language:
    """Detect if text is English, Chinese, or mixed based on character ranges."""
    if not text:
        return Language.UNKNOWN

    # Count Chinese characters (CJK Unified Ideographs)
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df\U0002a700-\U0002b73f\U0002b740-\U0002b81f\U0002b820-\U0002ceaf\uf900-\ufaff\u3300-\u33ff\ufe30-\ufe4f\uf900-\ufaff\U0002f800-\U0002fa1f]', text))
    
    # Count ASCII characters (English letters, numbers, basic punctuation)
    ascii_chars = len(re.findall(r'[a-zA-Z0-9\s\.,!?;:()\-"\'\[\]{}]', text))
    
    total_chars = len(text.strip())
    
    if total_chars == 0:
        return Language.UNKNOWN
    
    chinese_ratio = chinese_chars / total_chars
    ascii_ratio = ascii_chars / total_chars
    
    # If mostly Chinese (>30% Chinese chars and Chinese > ASCII)
    if chinese_ratio > 0.3 and chinese_ratio > ascii_ratio:
        return Language.CHINESE
    # If mostly English (>50% ASCII and ASCII > Chinese)
    elif ascii_ratio > 0.5 and ascii_ratio > chinese_ratio:
        return Language.ENGLISH
    # Otherwise mixed
    elif chinese_chars > 0 and ascii_chars > 0:
        return Language.MIXED
    # Fallback based on whichever has more
    elif chinese_chars > ascii_chars:
        return Language.CHINESE
    else:
        return Language.ENGLISH


async def is_ollama_available() -> bool:
    try:
        client = AsyncClient(host=OLLAMA_BASE_URL)
        await asyncio.wait_for(client.list(), timeout=5)
        return True
    except Exception:
        return False


# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """你是电报消息分类器。仅输出JSON，无markdown。

分类规则（按优先级）：
- job_posting：雇主/公司招聘。特征：列出多个职位/岗位、提供薪资待遇、含地点或包食宿、招聘联系方式。即使职位名称包含非工程师岗（产品/运营/DBA/技术总监）也算。
- personal_info：个人求职。必须同时满足：(1)第一人称求职语气（"求职"/"找工作"/"本人"/"我"），(2)描述自己的技能/经验年限/作品集/GitHub。若消息列出多个岗位名称，则为job_posting而非personal_info。
- other：非招聘内容，闲聊，广告，仅含联系方式无职位信息。

歧义处理：
- 消息同时含多个岗位名称（如"前端/java/产品/运维"）→ job_posting
- 消息含"包食宿"/"单休"/"双休" → job_posting

字段规则：
- skills：数组，非逗号字符串
- is_remote：true=远程，false=现场，null=未提及
- contacts：[{type,value}]，type可为telegram/email/linkedin/github/wechat/whatsapp/website/other
- confidence：high/medium/low
- translated_text：将原始消息完整翻译为英文。若原文已是英文，则输出null（不重复原文）。
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

        if total_input_length < 2048:
            num_ctx, num_predict = 2048, 2048
        else:
            num_ctx, num_predict = 4096, 4096

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

        # Detect language
        language = detect_language(message_text)
        logger.info("[OLLAMA] Detected language: %s", language.value)

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