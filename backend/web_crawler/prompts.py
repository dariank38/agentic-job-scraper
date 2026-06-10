"""RSS extraction prompt for job postings."""

# Generic RSS extraction prompt
RSS_PROMPT = """
You are analyzing job postings from RSS feed entries. Extract job postings from the provided text.

IMPORTANT INSTRUCTIONS:
1. Look for job postings in the RSS feed entries
2. Extract job details from titles, summaries, and content
3. Extract: job title, company name, salary range, location, requirements, deadline, URL
4. Identify if the job is remote or on-site
5. Extract contact information (emails, phone numbers, social links, contact persons)
6. Look for tech stack mentions (e.g., "Go", "Python", "React", etc.)
7. Return ONLY valid JSON - no explanations, no markdown

JSON Schema:
{{
  "job_postings": [
    {{
      "title": "string (job title, in English)",
      "company": "string or null (company name)",
      "location": "string or null (city or 'remote')",
      "requirements": "string or null (skills and experience requirements)",
      "salary": "string or null (salary range)",
      "deadline": "string or null",
      "url": "string or null (job URL)",
      "is_remote": "boolean or null (true if remote work mentioned)"
    }}
  ],
  "developer_info": {{
    "team_name": "string or null",
    "tech_stack": ["list of technologies mentioned"],
    "open_source_links": ["list of GitHub or repository URLs"],
    "description": "string or null"
  }},
  "contact_info": {{
    "emails": ["list of email addresses"],
    "phone_numbers": ["list of phone numbers"],
    "social_links": ["list of social links"],
    "contact_persons": ["list of contact names"]
  }}
}}

Text to analyze:
{content}
"""


# V2EX-specific prompt — each message is a single Chinese tech job post
V2EX_PROMPT = """
You are extracting a single job posting from a V2EX tech community post. The content may be in Chinese or English.

RULES:
- This is always ONE job posting per message — return exactly one object in job_postings
- Translate all extracted fields to English
- 远程 / remote / wfh = is_remote: true; 现场/onsite only = is_remote: false; not mentioned = null
- 招聘/诚聘/hiring/looking for = employer posting; ignore personal seeking posts (return empty job_postings)
- "title": job role name in English (e.g. "Backend Engineer", "Go Developer")
- "role_type": classify the role (frontend|backend|fullstack|devops|mobile|blockchain|smart_contract|data|ml_ai|qa|security|systems|embedded|other_tech)
- "requirements": translate skills, experience, and tech stack requirements to English
- "contacts": extract contact methods (email, telegram, linkedin, github, website) with type and value
- Return ONLY valid JSON - no explanations, no markdown

JSON Schema:
{{
  "job_postings": [
    {{
      "title": "string (job role in English)",
      "company": "string or null",
      "location": "string or null (city in English, or 'remote', or null)",
      "requirements": "string or null (translated skills and experience)",
      "salary": "string or null (e.g. '15k-25k CNY')",
      "deadline": "string or null",
      "url": "string or null",
      "is_remote": "boolean or null",
      "role_type": "string or null (frontend|backend|fullstack|devops|mobile|blockchain|smart_contract|data|ml_ai|qa|security|systems|embedded|other_tech)",
      "contacts": [
        {{"type": "string (email|telegram|linkedin|github|website|other)", "value": "string"}}
      ]
    }}
  ],
  "developer_info": null,
  "contact_info": {{
    "emails": [],
    "phone_numbers": [],
    "social_links": [],
    "contact_persons": []
  }}
}}

Post to analyze:
{content}
"""


def get_prompt_for_site(site_type: str = None, custom_prompt: str = None) -> str:
    """Get the appropriate prompt for extraction.

    Args:
        site_type: The site type — 'v2ex' uses V2EX-specific prompt.
        custom_prompt: Optional custom prompt override from database.

    Returns:
        The prompt to use for extraction.
    """
    if custom_prompt:
        return custom_prompt
    if site_type and site_type.lower() == "v2ex":
        return V2EX_PROMPT
    return RSS_PROMPT
