ASSISTANT_SYSTEM = """You are MailMind AI, an inbox assistant.
Use the provided email context to answer the user's question accurately and concisely.
If the context doesn't contain enough information, say so clearly."""

ASSISTANT_USER = """User question:
{question}

Inbox context:
{context}

Provide a helpful, actionable answer."""


def build_assistant_prompt(*, question: str, context: str) -> str:
    return ASSISTANT_USER.format(
        question=question[:1000],
        context=context[:12000],
    )
