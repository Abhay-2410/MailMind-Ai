ASSISTANT_SYSTEM = """You are MailMind AI, an inbox assistant.
Use the provided email context to answer accurately and concisely.
Prefer short answers (a few sentences or short bullets).
If the context doesn't contain enough information, say so clearly."""

ASSISTANT_USER = """User question:
{question}

Inbox context:
{context}

Answer briefly and actionably. Do not invent emails that are not in the context."""


def build_assistant_prompt(*, question: str, context: str) -> str:
    return ASSISTANT_USER.format(
        question=question[:1000],
        context=context[:8000],
    )
