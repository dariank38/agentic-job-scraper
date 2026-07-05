"""Data coercion helpers for mapping LLM JSON output to ORM fields."""

import re
from typing import Optional


def _first_contact(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                v = item.get("value")
                if v:
                    return v
            elif item:
                return str(item)
        return None
    if isinstance(value, dict):
        v = value.get("value")
        if v:
            return v
    return str(value)


def _first_contact_type(value) -> Optional[str]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                t = item.get("type")
                if t:
                    return t
        return None
    if isinstance(value, str):
        return value
    return None


def _to_str(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        processed = []
        for v in value:
            if isinstance(v, dict):
                val = v.get("value")
                if val:
                    processed.append(str(val))
            elif v:
                processed.append(str(v))
        return ", ".join(processed) or None
    if isinstance(value, dict):
        val = value.get("value")
        if val:
            return str(val)
    return str(value)


def _to_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        if value.lower() in ('false', 'no', '0', 'off'):
            return False
    if isinstance(value, list):
        return any(_to_bool(v) for v in value)
    return bool(value)


def _resolve_contact(contacts, message) -> tuple[Optional[str], Optional[str]]:
    contact = _first_contact(contacts)
    contact_type = _first_contact_type(contacts)
    if not contact:
        contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
        contact_type = "telegram" if contact else None
    return contact, contact_type


def _resolve_contacts(
    contacts,
    job_data: dict,
    channel_name: Optional[str],
    message,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve (hr_contact, channel_contact).

    - hr_contact: from AI's hr_contact field, or fallback to first contact in message.
    - channel_contact: channel username (e.g. zhixhaohr8), from channel_name arg or message.sender_username.
    """
    hr_contact = _to_str(job_data.get("hr_contact"))

    # Reject AI hr_contact if it doesn't look like a real contact handle
    # (must contain @, ., +, or be numeric — otherwise it's likely a garbled value)
    if hr_contact and not re.search(r"[@.+\d]", hr_contact):
        hr_contact = None

    if not hr_contact:
        raw_contact = _first_contact(contacts)
        if not raw_contact:
            raw_contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
        hr_contact = raw_contact

    channel_contact = _to_str(job_data.get("channel_contact"))
    if not channel_contact:
        channel_contact = channel_name or message.sender_username or (str(message.sender_id) if message.sender_id else None)

    return hr_contact, channel_contact


JOBEE_CATEGORIES = {
    "运营", "增长", "技术", "产品", "AI专项", "设计", "内容", "职能", "客服", "其他"
}


def _normalize_category(value) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip()
    if value in JOBEE_CATEGORIES:
        return value
    return "其他"


def _normalize_salary_level(value) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip().lower()
    if value in ("high", "normal", "negotiable"):
        return value
    return "negotiable"


def _normalize_priority(value) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip().upper()
    if value in ("P0", "P1", "P2"):
        return value
    return "P2"


_JD_PREFIXES = ("岗位职责：", "岗位职责:", "岗位描述：", "岗位描述:", "职责：", "职责:", "要求：", "要求:")

_JOB_TITLE_PATTERN = re.compile(r"\*{0,2}岗位速递[：:]\s*(.+?)\*{0,2}\s*(?:\n|$)")


def _extract_title(job_data: dict, message_text: Optional[str] = None) -> Optional[str]:
    """Extract a clean job title from AI output, message text, or JD fallback.

    Strategy:
    1. AI-provided title (if not a full paragraph)
    2. 岗位速递：Title pattern from message text
    3. First non-empty, non-prefix line from JD text
    4. First line from message text
    """
    # 1. AI title — reject if it looks like a JD paragraph (contains newlines or is too long)
    title = _to_str(job_data.get("title"))
    if title and "\n" not in title and len(title) <= 100:
        return title.strip()[:80]

    jd_text = _to_str(job_data.get("jd")) or _to_str(job_data.get("summary")) or ""

    # 2. Try 岗位速递：Title pattern from message text
    if message_text:
        clean = message_text.replace("<br/>", "\n").replace("<br>", "\n").replace("<p>", "\n").replace("</p>", "\n")
        m = _JOB_TITLE_PATTERN.search(clean)
        if m:
            extracted = m.group(1).strip().strip("*").strip()
            if extracted and len(extracted) <= 100:
                return extracted[:80]

    # 3. First non-empty, non-prefix line from JD
    if jd_text:
        for line in jd_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            for prefix in _JD_PREFIXES:
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break
            if line:
                return line[:80]

    # 4. First line from message text
    if message_text:
        clean = message_text.replace("<br/>", "\n").replace("<br>", "\n").replace("<p>", "\n").replace("</p>", "\n")
        for line in clean.split("\n"):
            line = line.strip().strip("*").strip()
            if line:
                return line[:80]

    return None
