"""Language detection utilities."""

import re
from enum import Enum


class Language(Enum):
    ENGLISH = "english"
    CHINESE = "chinese"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def detect_language(text: str) -> Language:
    if not text:
        return Language.UNKNOWN

    chinese_chars = len(re.findall(
        r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df\U0002a700-\U0002b73f'
        r'\U0002b740-\U0002b81f\U0002b820-\U0002ceaf\uf900-\ufaff\u3300-\u33ff'
        r'\ufe30-\ufe4f\U0002f800-\U0002fa1f]', text
    ))
    ascii_chars = len(re.findall(r'[a-zA-Z0-9\s\.,!?;:()\-"\'\[\]{}]', text))
    total_chars = len(text.strip())

    if total_chars == 0:
        return Language.UNKNOWN

    chinese_ratio = chinese_chars / total_chars
    ascii_ratio = ascii_chars / total_chars

    if chinese_ratio > 0.3 and chinese_ratio > ascii_ratio:
        return Language.CHINESE
    elif ascii_ratio > 0.5 and ascii_ratio > chinese_ratio:
        return Language.ENGLISH
    elif chinese_chars > 0 and ascii_chars > 0:
        return Language.MIXED
    elif chinese_chars > ascii_chars:
        return Language.CHINESE
    else:
        return Language.ENGLISH
