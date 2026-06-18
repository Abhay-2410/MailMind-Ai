REPLY_SYSTEM = """You are an email writing assistant for MailMind AI.
Write clear, context-aware email replies in the requested style.
Return only the reply body text, no subject line or metadata."""

REPLY_STYLES = {
    "professional": "Write in a professional, concise business tone.",
    "friendly": "Write in a warm, friendly but still professional tone.",
    "formal": "Write in a formal, polished tone suitable for official correspondence.",
    "short": "Write a brief, to-the-point reply in 2-4 sentences maximum.",
}

REPLY_USER = """Original email:

From: {sender}
Subject: {subject}

Body:
{body}

Write a {style} reply. {style_instruction}"""


def build_reply_prompt(
    *,
    sender: str,
    subject: str,
    body: str,
    style: str = "professional",
) -> str:
    style_key = style if style in REPLY_STYLES else "professional"
    return REPLY_USER.format(
        sender=sender,
        subject=subject,
        body=body[:6000],
        style=style_key,
        style_instruction=REPLY_STYLES[style_key],
    )
