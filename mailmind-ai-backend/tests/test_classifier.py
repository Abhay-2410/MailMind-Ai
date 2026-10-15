from app.models.category import CategorySource, EmailCategory
from app.services.classifier import (
    PRIORITY_THRESHOLD,
    ClassifierContext,
    classify,
    compute_priority,
    domain_matches,
    signals_from_fields,
    FINANCE_DOMAINS,
)


def _signals(**overrides):
    fields = {
        "sender": "someone@example.com",
        "subject": "",
        "preview": "",
        "labels": ["INBOX"],
    }
    fields.update(overrides)
    return signals_from_fields(**fields)


def test_domain_matches_subdomains_only_on_label_boundaries() -> None:
    assert domain_matches("alerts.axis.bank.in", FINANCE_DOMAINS)
    assert domain_matches("hdfcbank.net", FINANCE_DOMAINS)
    assert not domain_matches("disc.com", frozenset({"sc.com"}))


def test_bank_transaction_is_finance_even_in_updates_tab() -> None:
    result = classify(
        _signals(
            sender="alerts@hdfcbank.net",
            subject="Rs. 1,250.00 debited from your A/c XX1234",
            labels=["INBOX", "CATEGORY_UPDATES"],
            is_automated=True,
        ),
        ClassifierContext(),
    )
    assert result is not None
    assert result.category == EmailCategory.FINANCE
    assert result.source == CategorySource.RULE
    assert result.confidence >= 0.9


def test_bank_marketing_is_promotions() -> None:
    result = classify(
        _signals(
            sender="offers@hdfcbank.net",
            subject="Exclusive offer: flat 10% cashback on your card",
            labels=["INBOX", "CATEGORY_PROMOTIONS"],
            is_bulk=True,
        ),
        ClassifierContext(),
    )
    assert result is not None
    assert result.category == EmailCategory.PROMOTIONS


def test_contacted_person_on_consumer_domain_is_personal() -> None:
    result = classify(
        _signals(sender="friend@gmail.com", subject="Dinner on Friday?", labels=["INBOX", "CATEGORY_PERSONAL"]),
        ClassifierContext(user_email="me@gmail.com", contacted={"friend@gmail.com"}),
    )
    assert result is not None
    assert result.category == EmailCategory.PERSONAL


def test_sender_rule_overrides_everything() -> None:
    ctx = ClassifierContext(sender_rules={"news@shop.com": EmailCategory.UPDATES})
    result = classify(
        _signals(sender="news@shop.com", subject="50% off sale", labels=["CATEGORY_PROMOTIONS"], is_bulk=True),
        ctx,
    )
    assert result is not None
    assert result.category == EmailCategory.UPDATES
    assert result.source == CategorySource.SENDER_RULE


def test_sender_history_needs_enough_consistent_examples() -> None:
    weak = ClassifierContext(sender_history={"bot@site.com": (EmailCategory.WORK, 0.9, 2)})
    strong = ClassifierContext(sender_history={"bot@site.com": (EmailCategory.WORK, 0.9, 5)})
    signals = _signals(sender="bot@site.com", subject="Weekly digest")
    assert classify(signals, weak) is None
    result = classify(signals, strong)
    assert result is not None
    assert result.source == CategorySource.SENDER_HISTORY


def test_primary_tab_alone_is_low_confidence() -> None:
    result = classify(_signals(labels=["INBOX", "CATEGORY_PERSONAL"]), ClassifierContext())
    assert result is not None
    assert result.confidence < 0.75


def test_priority_is_independent_of_gmail_tab() -> None:
    ctx = ClassifierContext(contacted={"boss@corp.com"})
    starred_contact = _signals(sender="boss@corp.com", subject="Review", is_starred=True)
    newsletter = _signals(sender="news@shop.com", subject="Sale", is_bulk=True, is_important=True)
    assert compute_priority(starred_contact, EmailCategory.WORK, ctx) >= PRIORITY_THRESHOLD
    assert compute_priority(newsletter, EmailCategory.PROMOTIONS, ctx) < PRIORITY_THRESHOLD
