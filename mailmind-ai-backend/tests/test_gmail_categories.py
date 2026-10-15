from app.models.category import EmailCategory
from app.utils.gmail_categories import infer_category_from_gmail_labels


def test_infer_category_from_gmail_promotions() -> None:
    category = infer_category_from_gmail_labels(["INBOX", "CATEGORY_PROMOTIONS"])
    assert category == EmailCategory.PROMOTIONS


def test_infer_category_ignores_gmail_important_flag() -> None:
    category = infer_category_from_gmail_labels(["INBOX", "IMPORTANT", "CATEGORY_PROMOTIONS"])
    assert category == EmailCategory.PROMOTIONS


def test_infer_category_returns_none_for_inbox_only() -> None:
    assert infer_category_from_gmail_labels(["INBOX", "UNREAD"]) is None
