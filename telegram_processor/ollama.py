"""Ollama LLM analyzer for job message classification."""

import json
import asyncio
from typing import Any

import aiohttp

from telegram_processor.config import OLLAMA_BASE_URL, OLLAMA_MODEL

async def is_ollama_available() -> bool:
    """Check if Ollama server is accessible.

    Returns:
        True if Ollama is running and accessible, False otherwise.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{OLLAMA_BASE_URL}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                return response.status == 200
    except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
        return False
    except Exception:
        return False


SYSTEM_PROMPT = """You are a Telegram message analyzer for tech job boards. Analyze the message and categorize it. The message may be in any language — always respond in English JSON only.

CATEGORIES:
1. "job_posting" - Software/tech job posting (frontend, backend, fullstack, devops, mobile, blockchain, smart_contract, QA, data engineer, ML/AI engineer, etc.)
2. "personal_info" - Personal information of developers/engineers (skills, experience, portfolio, looking for work, etc.)
3. "other" - Non-tech content, marketing, sales, HR, design, etc.

RULES:
- ALWAYS translate the message to English in the "translated_text" field
- For job_posting: Extract job details (title, company, location, remote status, role type, skills, contact)
- For personal_info: Extract developer details (name, skills, experience, portfolio, github, linkedin, contact, looking_for_work)
- SKIP as "other" if: non-tech role, onsite-only jobs, marketing, sales, HR, design, community management, content writing, accounting

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
    "role_type": "frontend | backend | fullstack | devops | mobile | blockchain | smart_contract | data | ml_ai | qa | other_tech",
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
    "looking_for_work": true/false,
    "summary": ""
  }
}"""


async def analyze_message(text: str) -> dict[str, Any] | None:
    """Analyze a message using Ollama LLM.

    Args:
        text: The message text to analyze.

    Returns:
        Parsed JSON result or None if analysis fails.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    preview = text[:80].replace('\n', ' ')
    print(f"[Ollama] Sending: {preview}...")

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\nMessage to analyze:\n{text}",
        "stream": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
                if response.status != 200:
                    print(f"[Ollama] HTTP error: {response.status}")
                    return None

                data = await response.json()
                response_text = data.get("response", "")

                print(f"[Ollama] Raw response: {response_text[:200]}")

                # Extract JSON from response
                try:
                    result = json.loads(response_text)
                    print(f"[Ollama] Parsed: category={result.get('category')}, confidence={result.get('confidence')}")
                    return result
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    if "```json" in response_text:
                        json_part = response_text.split("```json")[1].split("```")[0]
                        result = json.loads(json_part.strip())
                        print(f"[Ollama] Parsed (json block): category={result.get('category')}")
                        return result
                    elif "```" in response_text:
                        json_part = response_text.split("```")[1].split("```")[0]
                        result = json.loads(json_part.strip())
                        print(f"[Ollama] Parsed (code block): category={result.get('category')}")
                        return result
                    else:
                        print(f"[Ollama] JSON parse failed, raw: {response_text[:300]}")
                        raise

    except aiohttp.ClientConnectorError as e:
        print(f"[Ollama] Connection error: {e}")
        return None
    except asyncio.TimeoutError:
        print(f"[Ollama] Timeout after 120s")
        return None
    except json.JSONDecodeError as e:
        print(f"[Ollama] JSON decode error: {e}")
        return None
    except Exception as e:
        print(f"[Ollama] Unexpected error: {e}")
        return None
