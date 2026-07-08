"""Async Ollama message analyzer."""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from ollama import AsyncClient

from app.routes.settings import get_ollama_model
from services.language import detect_language
from services.message_filter import SYSTEM_PROMPT, should_analyze_message
from telegram_processor.config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

RECOMMENDED_MODEL = "qwen2.5:14b"


class AsyncOllamaAnalyzer:
    def __init__(
        self,
        base_url: str = None,
        model_name: str = None,
        max_concurrent: int = None,
    ):
        self.client = AsyncClient(host=base_url or OLLAMA_BASE_URL)
        self.model_name = model_name
        self.max_concurrent = max_concurrent or int(os.getenv("OLLAMA_MAX_CONCURRENT", "3"))
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self._pending: int = 0

    def _get_model_options(self, message_length: int) -> dict:
        system_prompt_length = len(SYSTEM_PROMPT)
        total_input_length = message_length + system_prompt_length

        if total_input_length < 1500:
            num_ctx, num_predict = 2048, 2048
        elif total_input_length < 4000:
            num_ctx, num_predict = 4096, 4096
        else:
            num_ctx, num_predict = 8192, 8192

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
            return {"category": "other", "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

        language = detect_language(message_text)
        logger.info("[OLLAMA] Detected language: %s", language.value)

        clean_text = message_text[:4000]
        msg_preview = clean_text[:50]
        options = self._get_model_options(len(clean_text))

        self._pending += 1
        wait_start = time.monotonic()
        logger.info("[OLLAMA] Waiting for semaphore | pending: %d | msg: %.50s...", self._pending, clean_text)

        async with self.semaphore:
            self._pending -= 1
            wait_elapsed = time.monotonic() - wait_start
            process_start = time.monotonic()
            logger.info("[OLLAMA] Semaphore acquired | wait: %.1fs | msg: %.50s...", wait_elapsed, clean_text)

            try:
                model_name = self.model_name or get_ollama_model() or RECOMMENDED_MODEL
                response = await asyncio.wait_for(
                    self.client.generate(
                        model=model_name,
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
                    "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
                    "prompt_eval_duration": response.get("prompt_eval_duration", 0),
                    "eval_duration": response.get("eval_duration", 0),
                    "total_duration": response.get("total_duration", 0),
                }

                if usage["output_tokens"] >= options["num_predict"] * 0.9:
                    logger.warning("[OLLAMA] Output may be truncated: %d tokens", usage["output_tokens"])

                result = self._parse_json(response_text)
                result["usage"] = usage

                process_elapsed = time.monotonic() - process_start
                logger.info(
                    "[OLLAMA] Success | msg: %.50s... | category: %s | wait: %.1fs | process: %.1fs | tokens in/out: %d/%d",
                    clean_text, result.get("category", "unknown"), wait_elapsed, process_elapsed,
                    usage["input_tokens"], usage["output_tokens"],
                )
                return result

            except asyncio.TimeoutError:
                elapsed = time.monotonic() - process_start
                logger.error("[OLLAMA] TIMEOUT | msg: %.50s... | process time: %.1fs", msg_preview, elapsed)
                raise ValueError("Ollama request timed out after 300s")

            except json.JSONDecodeError as e:
                elapsed = time.monotonic() - process_start
                logger.error("[OLLAMA] JSON ERROR | msg: %.50s... | time: %.1fs | error: %s", msg_preview, elapsed, e)
                raise ValueError(f"JSON parse failed: {e}")

            except Exception as e:
                elapsed = time.monotonic() - process_start
                logger.error("[OLLAMA] ERROR | msg: %.50s... | time: %.1fs | error: %s", msg_preview, elapsed, e)
                raise

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for pattern in (r"```json\s*(.*?)```", r"```\s*(.*?)```"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
        raise json.JSONDecodeError("No valid JSON found", text, 0)
