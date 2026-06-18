CATEGORIZE_SYSTEM = """You are an email categorization assistant for MailMind AI.
Classify emails into exactly one category.
Always respond with valid JSON only."""

CATEGORIES = ["important", "work", "personal", "finance", "promotions", "social", "updates"]

CATEGORIZE_USER = """Categorize this email:

From: {sender}
Subject: {subject}

Preview:
{preview}

Valid categories: {categories}

Return JSON:
{{
  "category": "one of the valid categories",
  "confidence": 0.0 to 1.0
}}"""


def build_categorize_prompt(*, sender: str, subject: str, preview: str) -> str:
    return CATEGORIZE_USER.format(
        sender=sender,
        subject=subject,
        preview=preview[:2000],
        categories=", ".join(CATEGORIES),
    )


BATCH_CATEGORIZE_SYSTEM = """You are an email categorization assistant for MailMind AI.
Classify each email into exactly one category.
Always respond with valid JSON only."""

BATCH_CATEGORIZE_USER = """Categorize each of the following emails into exactly one category.

Valid categories: {categories}

Emails:
{emails}

Return JSON with this exact shape, one entry per email index:
{{
  "results": [
    {{ "index": 0, "category": "one of the valid categories", "confidence": 0.0 }}
  ]
}}"""


def build_batch_categorize_prompt(*, emails: list[dict]) -> str:
    lines = []
    for item in emails:
        preview = (item.get("preview") or "")[:300].replace("\n", " ")
        lines.append(
            f"[{item['index']}] From: {item.get('sender', '')} | "
            f"Subject: {item.get('subject', '')} | Preview: {preview}"
        )
    return BATCH_CATEGORIZE_USER.format(
        categories=", ".join(CATEGORIES),
        emails="\n".join(lines),
    )
