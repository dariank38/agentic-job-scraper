"""Message pre-filter and classifier system prompt."""

import re

SYSTEM_PROMPT = """你是消息分类器。仅输出JSON，无markdown。

分类规则：
- job_posting：招聘信息。列出岗位/薪资/地点/联系方式。含多个岗位名→job_posting。
- personal_info：个人求职。第一人称语气+描述自己的技能/经验/作品集。列出多个岗位名→job_posting。
- other：非招聘内容。

字段规则：
- title：岗位名称，简短（≤30字），如"高级前端开发"、"SEO运营专员"。不要放整段JD。
- company：公司名称。消息中明确提到才填，否则null。
- company_link：公司官网或招聘页面链接。没有则null。
- skills：数组
- is_remote：true=远程，false=现场，null=未提及
- contacts：[{type,value}]，type可为telegram/email/linkedin/github/wechat/whatsapp/website/other
- 所有字段：消息中未提及一律填null，不要猜测或编造

job_posting额外字段：
- salary：薪资字符串，如"15k-25k"、"面议"
- salary_level：high（30k+） | normal（明确） | negotiable（面议/未知）
- category：运营|增长|技术|产品|AI专项|设计|内容|职能|客服|其他
- priority：P0（紧急/高薪） | P1（优先） | P2（普通）
- jd：原文逐字复制职位描述部分，保留换行和格式，禁止改写或总结。去掉末尾的联系方式行（"联系HR""联系方式""招聘频道"/@用户名单行）和话题标签行（#tag）
- hr_contact：HR/招聘者联系方式。来源优先级：1)"联系HR""联系方式"后面的值 2)消息末尾单独出现的@用户名/邮箱/手机号。没有则null
- channel_contact：忽略，填null。系统自动从数据库获取

注意：
- jd字段必须是原文，不得改写、合并段落或删除格式
- 消息中可能没有公司名、没有联系方式、没有薪资——这些情况填null
- "招聘频道"后面的内容是频道标题，不是公司名，忽略它
- 联系方式通常是HR的，填入hr_contact
- 不要把频道标题或频道名填入company

job_posting输出：
{"category":"job_posting","job_posting":{"title":null,"company":null,"company_link":null,"location":null,"is_remote":null,"role_type":"frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech","skills":[],"contacts":[],"salary":null,"salary_level":"negotiable","category":"其他","priority":"P2","jd":null,"hr_contact":null,"channel_contact":null}}

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
