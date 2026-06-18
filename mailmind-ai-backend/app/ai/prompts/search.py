SEARCH_SYSTEM = """You are a Gmail search query translator for MailMind AI.
Convert natural language requests into valid Gmail search syntax.
Always respond with valid JSON only."""

SEARCH_USER = """Convert this natural language query to Gmail search syntax:

"{query}"

Return JSON:
{{
  "gmail_query": "valid gmail search string",
  "explanation": "brief explanation of the query"
}}

Examples:
- "Show unread Amazon emails" -> "from:amazon is:unread"
- "Emails received this week" -> "newer_than:7d"
- "Meeting requests from professors" -> "subject:meeting from:professor OR from:.edu"
"""


def build_search_prompt(*, query: str) -> str:
    return SEARCH_USER.format(query=query[:500])
