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


def infer_category_from_gmail_labels(labels: str | list[str] | None) -> EmailCategory | None:
    """Map Gmail tab labels to MailMind categories.

    Gmail's IMPORTANT flag is a priority signal, not a content category; it feeds
    priority_score instead (see classifier.compute_priority).
    """
    for label_id in parse_label_ids(labels):
        mapped = GMAIL_LABEL_TO_CATEGORY.get(label_id)
        if mapped is not None:
            return mapped
    return None
