"""RSS extraction prompt for job postings."""

# Generic RSS extraction prompt
RSS_PROMPT = """你是RSS招聘帖提取器。仅输出JSON，无markdown。

规则：
- 提取招聘信息：职位、公司、薪资、地点、要求、联系方式
- is_remote：true=远程，false=现场，null=未提及
- 所有字段翻译为英文
- 未知字段：null

输出：
{{"job_postings":[{{"title":"英文职位名","company":null,"location":null,"requirements":null,"salary":null,"deadline":null,"url":null,"is_remote":null}}],"developer_info":{{"team_name":null,"tech_stack":[],"open_source_links":[],"description":null}},"contact_info":{{"emails":[],"phone_numbers":[],"social_links":[],"contact_persons":[]}}}}

待分析内容：
{content}
"""


# V2EX-specific prompt — each message is a single Chinese tech job post
V2EX_PROMPT = """你是V2EX招聘帖提取器。仅输出JSON，无markdown。

规则：
- 每条消息仅一个招聘帖，返回一个job_postings对象
- 招聘/诚聘/hiring = 雇主发帖；求职帖返回空job_postings
- 所有字段翻译为英文
- is_remote：true=远程/wfh，false=现场，null=未提及
- role_type：frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech
- contacts：[{{type,value}}]，type可为email/telegram/linkedin/github/website/wechat/other
- 未知字段：null

输出：
{{"job_postings":[{{"title":"英文职位名","company":null,"location":null,"requirements":null,"salary":null,"deadline":null,"url":null,"is_remote":null,"role_type":null,"contacts":[]}}],"developer_info":null,"contact_info":{{"emails":[],"phone_numbers":[],"social_links":[],"contact_persons":[]}}}}

待分析帖子：
{content}
"""


# Eleduck-specific prompt — handles short plain text RSS descriptions
ELEDUCK_PROMPT = """你是电鸭社区招聘帖提取器。仅输出JSON，无markdown。

规则：
- 每条消息仅一个招聘帖，返回一个job_postings对象
- RSS描述可能被截断，提取可用信息即可
- 招聘/诚聘/hiring = 雇主发帖；求职帖返回空job_postings
- 所有字段翻译为英文
- is_remote：true=远程/wfh，false=现场，null=未提及
- role_type：frontend|backend|fullstack|devops|mobile|blockchain|data|ml_ai|qa|security|other_tech
- contacts：[{{type,value}}]，type可为email/telegram/linkedin/github/website/wechat/other
- 未知字段：null

输出：
{{"job_postings":[{{"title":"英文职位名","company":null,"location":null,"requirements":null,"salary":null,"deadline":null,"url":null,"is_remote":null,"role_type":null,"contacts":[]}}],"developer_info":null,"contact_info":{{"emails":[],"phone_numbers":[],"social_links":[],"contact_persons":[]}}}}

待分析RSS条目：
{content}
"""


def get_prompt_for_site(site_type: str = None, custom_prompt: str = None) -> str:
    """Get the appropriate prompt for extraction.

    Args:
        site_type: The site type — 'v2ex' uses V2EX-specific prompt, 'eleduck' uses ELEDUCK-specific prompt.
        custom_prompt: Optional custom prompt override from database.

    Returns:
        The prompt to use for extraction.
    """
    if custom_prompt:
        return custom_prompt
    if site_type and site_type.lower() == "v2ex":
        return V2EX_PROMPT
    if site_type and site_type.lower() == "eleduck":
        return ELEDUCK_PROMPT
    return RSS_PROMPT
