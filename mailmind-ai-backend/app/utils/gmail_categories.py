import json

from app.models.category import EmailCategory

GMAIL_LABEL_TO_CATEGORY: dict[str, EmailCategory] = {
    "CATEGORY_PROMOTIONS": EmailCategory.PROMOTIONS,
    "CATEGORY_SOCIAL": EmailCategory.SOCIAL,
    "CATEGORY_UPDATES": EmailCategory.UPDATES,
    "CATEGORY_PERSONAL": EmailCategory.PERSONAL,
    "CATEGORY_FORUMS": EmailCategory.SOCIAL,
}


def parse_label_ids(labels: str | list[str] | None) -> list[str]:
    if labels is None:
        return []
    if isinstance(labels, list):
        return labels
    try:
        parsed = json.loads(labels)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def infer_category_from_gmail_labels(
    labels: str | list[str] | None,
    *,
    is_important: bool = False,
) -> EmailCategory | None:
    """Map Gmail tab/category labels to MailMind categories."""
    label_ids = parse_label_ids(labels)

    if is_important or "IMPORTANT" in label_ids:
        return EmailCategory.IMPORTANT

    for label_id in label_ids:
        mapped = GMAIL_LABEL_TO_CATEGORY.get(label_id)
        if mapped is not None:
            return mapped

    return None
