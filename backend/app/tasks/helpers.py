"""Data coercion helpers for mapping LLM JSON output to ORM fields."""

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
    """Resolve (hr_contact, channel_contact) from AI output + fallbacks.

    Prefer explicit AI fields (hr_contact, channel_contact).
    Fallback: classify the contacts list by type.
    """
    hr_contact = _to_str(job_data.get("hr_contact"))
    channel_contact = _to_str(job_data.get("channel_contact"))

    raw_contact = _first_contact(contacts)
    raw_contact_type = _first_contact_type(contacts)

    if not raw_contact:
        raw_contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
        raw_contact_type = "telegram" if raw_contact else None

    if not channel_contact:
        if raw_contact_type in ("telegram", "channel") and raw_contact:
            channel_contact = raw_contact
        elif raw_contact:
            channel_contact = raw_contact
        else:
            channel_contact = channel_name or message.sender_username or (str(message.sender_id) if message.sender_id else None)

    if not hr_contact:
        if raw_contact and raw_contact_type not in ("telegram", "channel"):
            hr_contact = raw_contact

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
