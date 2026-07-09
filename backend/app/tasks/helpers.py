"""Data coercion helpers for mapping LLM JSON output to ORM fields."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


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


def _infer_contact_type(value: Optional[str], ai_type: Optional[str] = None) -> str:
    """Infer contact type from value or AI-provided type."""
    VALID = {"telegram", "email", "phone", "wechat", "website", "other"}
    if ai_type and ai_type in VALID:
        return ai_type
    if not value:
        return "telegram"
    v = value.strip()
    if v.startswith("@") or re.match(r"^https?://t\.me/", v):
        return "telegram"
    if re.match(r"[^@]+@[^@]+\.[^@]+", v):
        return "email"
    if re.match(r"^\+?\d[\d\s\-]{6,}$", v):
        return "phone"
    if re.match(r"^https?://", v):
        return "website"
    return "telegram"


def _resolve_contacts(
    contacts,
    job_data: dict,
    channel_name: Optional[str],
    message,
) -> tuple[Optional[str], Optional[str], str, str]:
    """Resolve (hr_contact, channel_contact, hr_contact_type, channel_contact_type).

    - hr_contact: from AI's hr_contact field, or fallback to first contact in message.
    - channel_contact: channel username, from channel_name arg or message.sender_username.
    """
    hr_contact = _to_str(job_data.get("hr_contact"))

    # Reject AI hr_contact if it doesn't look like a real contact handle
    if hr_contact and not re.search(r"[@.+\d]", hr_contact):
        hr_contact = None

    ai_hr_type = _first_contact_type(contacts) if not hr_contact else None

    if not hr_contact:
        raw_contact = _first_contact(contacts)
        ai_hr_type = _first_contact_type(contacts)
        if not raw_contact:
            raw_contact = message.sender_username or (str(message.sender_id) if message.sender_id else None)
            ai_hr_type = "telegram"
        hr_contact = raw_contact

    hr_contact_type = _infer_contact_type(hr_contact, ai_hr_type)

    channel_contact = _to_str(job_data.get("channel_contact"))
    if not channel_contact:
        channel_contact = channel_name or message.sender_username or (str(message.sender_id) if message.sender_id else None)
    channel_contact_type = _infer_contact_type(channel_contact, "telegram")

    logger.debug(
        "[contacts] resolved hr=%r (%s) channel=%r (%s) | channel_name_arg=%r sender_username=%r",
        hr_contact, hr_contact_type, channel_contact, channel_contact_type,
        channel_name, getattr(message, "sender_username", None),
    )
    return hr_contact, channel_contact, hr_contact_type, channel_contact_type


JOBEE_CATEGORIES = {
    "运营", "增长", "技术", "产品", "AI专项", "设计", "内容", "职能", "客服", "其他"
}


# Common English/Chinese keywords mapped to canonical Jobees categories.
# Order matters: earlier categories are checked first (e.g., AI before general tech).
_CATEGORY_KEYWORDS = [
    ("AI专项", {"ai", "artificial intelligence", "machine learning", "deep learning", "ml", "大模型", "llm", "nlp", "自然语言处理", "计算机视觉", "cv", "aigc", "生成式", "生成式ai", "多模态", "强化学习", "算法", "数据科学", "data scientist", "scientist", "quant", "量化", "推荐算法", "搜索算法"}),
    ("技术", {"tech", "technology", "engineering", "software", "developer", "开发", "程序", "程序员", "工程", "工程师", "frontend", "backend", "fullstack", "full-stack", "devops", "mobile", "blockchain", "security", "qa", "data", "cloud", "sre", "运维", "测试", "安全", "区块链", "web", "全栈", "前端", "后端", "移动", "大数据", "云计算", "云原生", "架构师", "架构", "cto", "首席技术官", "技术负责人", "技术经理", "技术总监"}),
    ("产品", {"产品", "product", "产品经理", "产品专员", "产品负责人", "产品总监", "产品设计"}),
    ("设计", {"设计", "design", "ui", "ux", "graphic", "平面", "视觉", "交互", "工业设计", "ui设计", "ux设计", "视觉设计", "平面设计", "原画", "插画", "动画", "动效", "设计师"}),
    ("运营", {"运营", "operation", "operations", "市场运营", "新媒体运营", "社群运营", "活动运营", "用户运营", "内容运营"}),
    ("增长", {"增长", "growth", "增长运营", "用户增长", "业务增长"}),
    ("内容", {"内容", "content", "编辑", "文案", "写手", "新媒体", "自媒体", "内容运营", "内容编辑", "内容创作", "文案策划", "内容策划", "主播", "短视频", "视频", "直播", "导演", "编剧", "记者", "媒介", "公关", "品牌"}),
    ("职能", {"职能", "hr", "human resources", "人力资源", "人事", "行政", "财务", "会计", "出纳", "法务", "legal", "采购", "供应链", "物流", "招聘", "前台", "manager", "management", "project manager", "项目管理", "经理", "主管", "总监", "高管"}),
    ("客服", {"客服", "customer service", "support", "售后", "售前", "客户支持", "客户关系", "helpdesk", "呼叫中心", "在线客服", "用户支持"}),
]


def _normalize_category(value) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip()
    if value in JOBEE_CATEGORIES:
        return value

    normalized = value.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return category
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
