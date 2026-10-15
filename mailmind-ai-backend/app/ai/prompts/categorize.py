CATEGORIES = ["work", "personal", "finance", "promotions", "social", "updates"]

CATEGORY_GUIDE = """Categories (choose exactly one):
- work: jobs, school/college/university, clients, colleagues, recruiters, interviews, job applications, professional projects, meetings.
- personal: written by a real person to the user personally (friends, family, personal plans). Never automated mail.
- finance: money and financial accounts — bank/card/UPI transaction alerts, statements, bills, invoices, payment receipts, refunds, investments, taxes, insurance, loans.
- promotions: marketing whose goal is selling — sales, offers, discounts, coupons, product launches, promotional newsletters.
- social: social networks and communities — notifications from Facebook, Instagram, LinkedIn, Reddit, X, Discord, forums, comments, friend/connection requests.
- updates: automated non-marketing notices — shipping/delivery, account and security alerts, OTPs, service/app notifications, confirmations, non-sales digests.

Tie-break rules:
- A bank or payment provider reporting a transaction, balance or statement is finance even though it is automated. A bank advertising a card or loan is promotions.
- A receipt or invoice for a payment is finance; shipping or delivery tracking for the same order is updates.
- Recruiter outreach, interview scheduling and application status are work; mass job-alert digests are updates.
- If a real person writes and "you_emailed_sender" is true, it is personal or work — never updates or promotions.
- "bulk" means the message carries mailing-list headers; bulk mail is almost never personal.
- Use the "current_guess" only as a hint; override it when the content clearly says otherwise.

Confidence: 0.9+ only when the content makes the category unambiguous; 0.5-0.7 when two categories are plausible."""

CATEGORIZE_SYSTEM = f"""You are an email categorization assistant for MailMind AI.
Classify the email into exactly one category.
{CATEGORY_GUIDE}
Always respond with valid JSON only."""

CATEGORIZE_USER = """Categorize this email:

From: {sender}
Subject: {subject}
Signals: {signals}

Preview:
{preview}

Return JSON:
{{
  "category": "one of: {categories}",
  "confidence": 0.0 to 1.0
}}"""


def build_categorize_prompt(
    *,
    sender: str,
    subject: str,
    preview: str,
    signals: str = "none",
) -> str:
    return CATEGORIZE_USER.format(
        sender=sender,
        subject=subject,
        preview=preview[:2000],
        signals=signals,
        categories=", ".join(CATEGORIES),
    )


BATCH_CATEGORIZE_SYSTEM = f"""You are an email categorization assistant for MailMind AI.
Classify each email into exactly one category.
{CATEGORY_GUIDE}
Always respond with valid JSON only."""

BATCH_CATEGORIZE_USER = """{examples}Categorize each of the following emails.

Valid categories: {categories}

Emails:
{emails}

Return JSON with this exact shape, one entry per email index:
{{
  "results": [
    {{ "index": 0, "category": "one of the valid categories", "confidence": 0.0 }}
  ]
}}"""


def format_signals(item: dict) -> str:
    parts: list[str] = []
    if item.get("gmail_tab"):
        parts.append(f"gmail_tab={item['gmail_tab']}")
    if item.get("bulk"):
        parts.append("bulk")
    if item.get("automated"):
        parts.append("automated")
    if item.get("you_emailed_sender"):
        parts.append("you_emailed_sender")
    if item.get("current_guess"):
        parts.append(f"current_guess={item['current_guess']}")
    return ", ".join(parts) or "none"


def build_batch_categorize_prompt(*, emails: list[dict], examples: list[dict] | None = None) -> str:
    lines = []
    for item in emails:
        preview = (item.get("preview") or "")[:240].replace("\n", " ")
        lines.append(
            f"[{item['index']}] From: {item.get('sender_name') or ''} <{item.get('sender', '')}> | "
            f"Subject: {item.get('subject', '')} | Signals: {format_signals(item)} | Preview: {preview}"
        )

    examples_block = ""
    if examples:
        example_lines = [
            f"- <{example['sender']}> \"{example['subject'][:120]}\" -> {example['category']}"
            for example in examples
        ]
        examples_block = (
            "This user corrected these emails themselves; follow the same conventions:\n"
            + "\n".join(example_lines)
            + "\n\n"
        )

    return BATCH_CATEGORIZE_USER.format(
        examples=examples_block,
        categories=", ".join(CATEGORIES),
        emails="\n".join(lines),
    )
