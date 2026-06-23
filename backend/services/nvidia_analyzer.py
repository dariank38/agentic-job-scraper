"""Async NVIDIA NIM message analyzer — drop-in replacement for AsyncOllamaAnalyzer."""

import json
import logging
import os
import time
from typing import Any

import httpx

from services.language import detect_language
from services.message_filter import SYSTEM_PROMPT, should_analyze_message

logger = logging.getLogger(__name__)

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_ANALYZE_MODEL = os.environ.get("NVIDIA_MODEL", "qwen/qwen3.5-397b-a17b")


class AsyncNvidiaAnalyzer:
    @property
    def model_name(self) -> str:
        from app.routes.settings import get_nvidia_model
        return get_nvidia_model()

    async def analyze_message(self, message_text: str) -> dict[str, Any]:
        if not should_analyze_message(message_text):
            return {"category": "other", "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

        language = detect_language(message_text)
        clean_text = " ".join(message_text.split())[:2000]
        msg_preview = clean_text[:50]

        msg_len = len(clean_text)
        system_prompt_length = len(SYSTEM_PROMPT)
        total_input_length = msg_len + system_prompt_length

        max_tokens = 1024 if total_input_length < 1500 else 2048

        logger.info(
            "[NVIDIA] Message: %d chars | System prompt: %d chars | Total: %d chars | max_tokens: %d | lang: %s",
            msg_len, system_prompt_length, total_input_length, max_tokens, language.value,
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": clean_text},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "top_p": 0.9,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=5.0)
            ) as client:
                response = await client.post(NVIDIA_INVOKE_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            choices = data.get("choices")
            if not choices:
                logger.error("[NVIDIA] Empty choices | raw response: %s", json.dumps(data)[:500])
                raise ValueError(f"NVIDIA returned no choices: {data.get('error', data)}")

            choice = choices[0]
            finish_reason = choice.get("finish_reason")
            message = choice.get("message", {})
            raw = message.get("content", "").strip()
            usage_data = data.get("usage", {})

            if not raw:
                if finish_reason == "stop":
                    logger.warning(
                        "[NVIDIA] Empty content with finish_reason=stop (content filter/refusal) | msg: %.50s... — returning 'other'",
                        msg_preview,
                    )
                    prompt_tokens = usage_data.get("prompt_tokens", 0)
                    return {"category": "other", "usage": {"input_tokens": prompt_tokens, "output_tokens": 0, "total_tokens": prompt_tokens}}
                logger.error(
                    "[NVIDIA] Empty content | finish_reason: %s | raw response: %s",
                    finish_reason, json.dumps(data)[:500],
                )
                raise ValueError(f"NVIDIA returned empty content (finish_reason={finish_reason})")

            if finish_reason == "length":
                logger.warning(
                    "[NVIDIA] Output truncated (finish_reason=length) | max_tokens=%d | msg: %.50s...",
                    max_tokens, msg_preview,
                )

            usage = {
                "input_tokens": usage_data.get("prompt_tokens", 0),
                "output_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }

            from services.ollama_analyzer import AsyncOllamaAnalyzer
            result = AsyncOllamaAnalyzer._parse_json(raw)
            result["usage"] = usage

            elapsed = time.monotonic() - start
            logger.info(
                "[NVIDIA] Success | msg: %.50s... | category: %s | finish: %s | time: %.1fs | tokens in/out: %d/%d",
                clean_text, result.get("category", "unknown"), finish_reason, elapsed,
                usage["input_tokens"], usage["output_tokens"],
            )
            return result

        except httpx.HTTPStatusError as e:
            elapsed = time.monotonic() - start
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("retry-after", 60))
                logger.warning(
                    "[NVIDIA] RATE LIMITED (429) | msg: %.50s... | retry-after: %ds",
                    msg_preview, retry_after,
                )
                import asyncio as _asyncio
                await _asyncio.sleep(retry_after)
                raise ValueError(f"NVIDIA rate limited (429), retry after {retry_after}s")
            logger.error("[NVIDIA] HTTP ERROR %d | msg: %.50s... | time: %.1fs", e.response.status_code, msg_preview, elapsed)
            raise
        except httpx.ReadTimeout:
            elapsed = time.monotonic() - start
            logger.error("[NVIDIA] TIMEOUT (read) | msg: %.50s... | time: %.1fs", msg_preview, elapsed)
            raise ValueError(f"NVIDIA API read timed out after {elapsed:.0f}s (limit: 300s)")
        except httpx.TimeoutException as e:
            elapsed = time.monotonic() - start
            logger.error("[NVIDIA] TIMEOUT | msg: %.50s... | time: %.1fs | error: %s", msg_preview, elapsed, e)
            raise ValueError(f"NVIDIA API timed out after {elapsed:.0f}s: {e}")
        except json.JSONDecodeError as e:
            logger.error("[NVIDIA] JSON ERROR | msg: %.50s... | error: %s", msg_preview, e)
            raise ValueError(f"JSON parse failed: {e}")
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("[NVIDIA] ERROR | msg: %.50s... | time: %.1fs | error: %s", msg_preview, elapsed, e)
            raise
