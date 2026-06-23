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
    if isinstance(value, list):
        return any(v if isinstance(v, bool) else bool(v) for v in value)
    return bool(value)


def _resolve_contact(contacts, message) -> tuple[Optional[str], Optional[str]]:
    contact = _first_contact(contacts)
    contact_type = _first_contact_type(contacts)
    if not contact:
        contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
        contact_type = "telegram" if contact else None
    return contact, contact_type
