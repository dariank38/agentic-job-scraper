"""Message pre-filter and classifier system prompt."""

import re

SYSTEM_PROMPT = """你是严格的消息分类器。仅输出JSON，无markdown，无解释。

## 分类标准（严格）

**job_posting** — 必须同时满足：
1. 明确招募他人（第三人称招聘语气，如"招聘""诚招""急招""我们在招"）
2. 包含具体岗位名称（如"前端开发""运营专员"）
3. 包含以下至少一项：薪资 / 工作职责 / 任职要求 / 联系方式

**personal_info** — 必须同时满足：
1. 第一人称自我介绍（如"我是""本人""在找""求职"）
2. 描述自身技能、经验或作品集

**other** — 以下任何情况直接返回 other，不得分类为 job 或 personal：
- 仅有日期/更新公告（如"X月X日热门岗位更新"）
- 仅有话题标签（#招聘 #远程）
- 乱码、重复文本、无意义内容
- 广告、通知、群公告、转发提醒
- 闲聊、问候、表情符号为主
- 内容不足以判断，或无实质岗位信息
- **不确定时一律选 other**

## 字段规则（仅适用于 job_posting / personal_info）
- 所有字段：消息中未明确提及→填null，禁止猜测或编造
- title：岗位名称，≤30字，不放整段描述
- company：公司名。消息明确提到才填，否则null。频道名/频道标题不是公司名
- jd：原文逐字复制职位描述，保留换行和格式，禁止改写。去掉末尾联系方式行和#tag行
- hr_contact：优先取"联系HR/联系方式"后的值；其次取消息末尾单独出现的@用户名/邮箱/手机号；没有则null
- channel_contact：填null（系统自动获取）
- contacts：[{type,value}]，type: telegram/email/linkedin/github/wechat/whatsapp/website/other
- is_remote：true=远程，false=现场，null=未提及
- salary_level：high（≥30k）| normal（明确金额）| negotiable（面议/未知）
- priority：仅限 P0 / P1 / P2（这是我们的紧急度标记，不是JD中的职级）。P0=紧急招聘或高薪≥30k，P1=优质岗位，P2=普通。JD中出现的"P3""P4""P5"等是职级，不要填入此字段
- category：必须为以下之一（不要输出任何其他值）：运营 / 增长 / 技术 / 产品 / AI专项 / 设计 / 内容 / 职能 / 客服 / 其他。根据岗位核心类型判断；技术岗位若聚焦AI/算法/大模型，则归类为"AI专项"

## 输出格式

job_posting：
{"category":"job_posting","job_posting":{"title":null,"company":null,"company_link":null,"location":null,"is_remote":null,"role_type":"frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech","skills":[],"contacts":[],"salary":null,"salary_level":"negotiable","category":"其他","priority":"P2","jd":null,"hr_contact":null,"channel_contact":null}}

personal_info：
{"category":"personal_info","personal_info":{"name":null,"skills":[],"experience":null,"portfolio":null,"github":null,"linkedin":null,"contacts":[],"looking_for_work":null,"summary":null}}

other：
{"category":"other"}"""


_SPAM_PATTERN = re.compile(
    r"airdrop|casino|gambling|betting|forex|trading.signal|dropshipping|\bmlm\b|"
    r"赌博|博彩|外汇|微商",
    re.IGNORECASE,
)

_MIN_LENGTH = 30

_HASHTAG_ONLY = re.compile(r"^(\s*#\w+\s*)+$")

_JOB_KEYWORDS = re.compile(
    r"招聘|职位|薪资|薪水|工资|简历|应聘|求职|职责|要求|经验|技能|skill|job|hire|salary|remote|"
    r"k/月|k月|万/月|面议|全职|兼职|实习|@\w+|t\.me/|\w+@\w+\.\w+|\+\d{7,}",
    re.IGNORECASE,
)

_ANNOUNCEMENT_PATTERN = re.compile(
    r"^[\s\*⚡🔥📢📣💼✨🌟🎯]+.*?(更新|汇总|速递|精选|推荐|通知|公告|预告|发布|上新)[\s\*⚡🔥📢📣💼✨🌟🎯]*$",
    re.IGNORECASE,
)


def should_analyze_message(text: str) -> bool:
    if not text or len(text.strip()) < _MIN_LENGTH:
        return False
    if _SPAM_PATTERN.search(text):
        return False
    stripped = text.strip()
    if _HASHTAG_ONLY.match(stripped):
        return False
    if _ANNOUNCEMENT_PATTERN.match(stripped):
        return False
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if lines:
        if len(lines) == 1 and len(lines[0]) < 60:
            return False
        most_common_count = max(lines.count(l) for l in set(lines))
        if most_common_count >= 3:
            return False
        unique_ratio = len(set(lines)) / len(lines)
        if len(lines) >= 5 and unique_ratio < 0.4:
            return False
    if not _JOB_KEYWORDS.search(text):
        return False
    return True
