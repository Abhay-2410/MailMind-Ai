SUMMARIZE_SYSTEM = """You are an email assistant for MailMind AI.
Summarize emails clearly and extract structured metadata.
Always respond with valid JSON only."""

SUMMARIZE_USER = """Summarize this email:

From: {sender}
Subject: {subject}
Date: {received_at}

Body:
{body}

Return JSON with this exact structure:
{{
  "summary_text": "2-3 sentence overview",
  "key_points": ["point 1", "point 2"],
  "action_items": ["action 1"],
  "important_dates": ["date or deadline if any"],
  "priority_level": "low|medium|high|urgent"
}}"""


def build_summarize_prompt(*, sender: str, subject: str, received_at: str, body: str) -> str:
    return SUMMARIZE_USER.format(
        sender=sender,
        subject=subject,
        received_at=received_at,
        body=body[:8000],
    )
