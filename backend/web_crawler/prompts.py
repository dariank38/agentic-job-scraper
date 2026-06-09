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
      "title": "string (job title)",
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


def get_prompt_for_site(site_type: str = None, custom_prompt: str = None) -> str:
    """Get the appropriate prompt for extraction.

    Args:
        site_type: The site type (ignored for generic RSS).
        custom_prompt: Optional custom prompt from database

    Returns:
        The prompt to use for extraction.
    """
    if custom_prompt:
        return custom_prompt
    return RSS_PROMPT
