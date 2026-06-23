"""Message pre-filter and classifier system prompt."""

import re

SYSTEM_PROMPT = """你是电报消息分类器。仅输出JSON，无markdown。

分类规则（按优先级）：
- job_posting：雇主/公司招聘。特征：列出多个职位/岗位、提供薪资待遇、含地点或包食宿、招聘联系方式。即使职位名称包含非工程师岗（产品/运营/DBA/技术总监）也算。
- personal_info：个人求职。必须同时满足：(1)第一人称求职语气（"求职"/"找工作"/"本人"/"我"），(2)描述自己的技能/经验年限/作品集/GitHub。若消息列出多个岗位名称，则为job_posting而非personal_info。
- other：非招聘内容，闲聊，广告，仅含联系方式无职位信息。

歧义处理：
- 消息同时含多个岗位名称（如"前端/java/产品/运维"）→ job_posting
- 消息含"包食宿"/"单休"/"双休" → job_posting

字段规则：
- skills：数组，非逗号字符串
- is_remote：true=远程，false=现场，null=未提及
- contacts：[{type,value}]，type可为telegram/email/linkedin/github/wechat/whatsapp/website/other
- confidence：high/medium/low
- translated_text：将原始消息完整翻译为英文。若原文已是英文，则输出null（不重复原文）。
- 未知字段：null

job_posting输出：
{"category":"job_posting","confidence":"...","translated_text":"...","job_posting":{"company":null,"company_link":null,"location":null,"is_remote":null,"role_type":"frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech","skills":[],"contacts":[],"summary":null}}

personal_info输出：
{"category":"personal_info","confidence":"...","translated_text":"...","personal_info":{"name":null,"skills":[],"experience":null,"portfolio":null,"github":null,"linkedin":null,"contacts":[],"looking_for_work":null,"summary":null}}

other输出：
{"category":"other","confidence":"..."}"""


_SPAM_PATTERN = re.compile(
    r"airdrop|casino|gambling|betting|forex|trading.signal|dropshipping|\bmlm\b|"
    r"赌博|博彩|外汇|微商",
    re.IGNORECASE,
)

_MIN_LENGTH = 20


def should_analyze_message(text: str) -> bool:
    if not text or len(text.strip()) < _MIN_LENGTH:
        return False
    if _SPAM_PATTERN.search(text):
        return False
    return True
