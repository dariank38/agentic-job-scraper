"""Message pre-filter and classifier system prompt."""

import re

SYSTEM_PROMPT = """你是消息分类器。仅输出JSON，无markdown。

分类规则：
- job_posting：招聘。列出岗位/薪资/地点/联系方式。含多个岗位名→job_posting。
- personal_info：个人求职。第一人称语气+描述自己的技能/经验/作品集。列出多个岗位名→job_posting。
- other：非招聘内容。

字段规则：
- skills：数组
- is_remote：true=远程，false=现场，null=未提及
- contacts：[{type,value}]，type可为telegram/email/linkedin/github/wechat/whatsapp/website/other
- 未知填null

job_posting额外字段：
- salary：薪资字符串，如"15k-25k"、"面议"
- salary_level：high（30k+） | normal（明确） | negotiable（面议/未知）
- category：运营|增长|技术|产品|AI专项|设计|内容|职能|客服|其他
- priority：P0（紧急/高薪） | P1（优先） | P2（普通）
- jd：完整职位描述，优先原文
- hr_contact：HR联系方式（邮箱/Telegram/手机号）
- channel_contact：发布渠道联系方式。仅一种联系方式时填channel_contact，hr_contact填null

job_posting输出：
{"category":"job_posting","job_posting":{"company":null,"company_link":null,"location":null,"is_remote":null,"role_type":"frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech","skills":[],"contacts":[],"salary":null,"salary_level":"negotiable","category":"其他","priority":"P2","jd":null,"hr_contact":null,"channel_contact":null}}

personal_info输出：
{"category":"personal_info","personal_info":{"name":null,"skills":[],"experience":null,"portfolio":null,"github":null,"linkedin":null,"contacts":[],"looking_for_work":null,"summary":null}}

other输出：
{"category":"other"}"""


_SPAM_PATTERN = re.compile(
    r"airdrop|casino|gambling|betting|forex|trading.signal|dropshipping|\bmlm\b|"
    r"赌博|博彩|外汇|微商",
    re.IGNORECASE,
)

_MIN_LENGTH = 30


def should_analyze_message(text: str) -> bool:
    if not text or len(text.strip()) < _MIN_LENGTH:
        return False
    if _SPAM_PATTERN.search(text):
        return False
    return True
