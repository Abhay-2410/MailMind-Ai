"""Deterministic, explainable email classification (no network / AI calls).

Layers, strongest first: user sender rules > high-precision rules (finance, social,
bulk marketing, people you write to) > sender history > Gmail tab labels. Anything
below AI_CONFIDENCE_THRESHOLD is handed to the AI layer (categorization_service).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.category import CategorySource, EmailCategory
from app.utils.gmail_categories import parse_label_ids

AI_CONFIDENCE_THRESHOLD = 0.75
PRIORITY_THRESHOLD = 60
SENDER_HISTORY_MIN_EMAILS = 3
SENDER_HISTORY_MIN_SHARE = 0.8

CONTENT_CATEGORIES: tuple[EmailCategory, ...] = (
    EmailCategory.WORK,
    EmailCategory.PERSONAL,
    EmailCategory.FINANCE,
    EmailCategory.PROMOTIONS,
    EmailCategory.SOCIAL,
    EmailCategory.UPDATES,
)

CONSUMER_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "ymail.com",
        "outlook.com", "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com",
        "mac.com", "proton.me", "protonmail.com", "aol.com", "rediffmail.com",
        "zoho.com", "zohomail.in", "gmx.com", "mail.com", "yandex.com",
    }
)

FINANCE_DOMAINS = frozenset(
    {
        # Indian banks
        "axisbank.com", "axis.bank.in", "hdfcbank.net", "hdfcbank.com", "hdfc.bank.in",
        "icicibank.com", "icici.bank.in", "sbi.co.in", "sbi.bank.in", "onlinesbi.com",
        "sbicard.com", "kotak.com", "kotak.bank.in", "yesbank.in", "idfcfirstbank.com",
        "indusind.com", "bankofbaroda.com", "bankofbaroda.co.in", "pnb.co.in",
        "canarabank.com", "unionbankofindia.co.in", "federalbank.co.in", "aubank.in",
        "rblbank.com", "sc.com", "hsbc.co.in", "citi.com", "americanexpress.com", "aexp.com",
        # Payments / wallets
        "paytm.com", "phonepe.com", "razorpay.com", "cashfree.com", "payu.in",
        "mobikwik.com", "cred.club", "paypal.com", "stripe.com", "wise.com", "revolut.com",
        "amazonpay.in", "billdesk.com", "npci.org.in", "venmo.com", "cash.app",
        # Investments / tax
        "zerodha.com", "zerodha.net", "groww.in", "upstox.com", "angelone.in",
        "kfintech.com", "camsonline.com", "nsdl.co.in", "cdslindia.com", "cdslindia.co.in",
        "nseindia.com", "nse.co.in", "bseindia.com", "mfcentral.com", "smallcase.com", "indmoney.com", "etmoney.com",
        "incometax.gov.in", "gst.gov.in", "robinhood.com", "fidelity.com", "vanguard.com",
        "schwab.com", "coinbase.com",
        # Global banks
        "chase.com", "bankofamerica.com", "wellsfargo.com", "capitalone.com", "discover.com",
    }
)

SOCIAL_DOMAINS = frozenset(
    {
        "facebookmail.com", "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
        "x.com", "redditmail.com", "reddit.com", "quora.com", "pinterest.com", "discord.com",
        "tiktok.com", "snapchat.com", "threads.net", "whatsapp.com", "telegram.org",
        "meetup.com", "tumblr.com", "mastodon.social", "bsky.app",
    }
)

FINANCE_TRANSACTION_RE = re.compile(
    r"\b(debited|credited|a/c|acct|account (no|number|statement)|transaction|txn|upi|neft|"
    r"imps|rtgs|e-?statement|statement|invoice|receipt|payment (of|received|successful|failed|"
    r"due|reminder|confirmation)|refund(ed)?|emi|bill (generated|is due|payment)|amount due|"
    r"auto-?debit|mandate|sip|dividend|income tax|tds|gst)\b",
    re.IGNORECASE,
)
CURRENCY_RE = re.compile(r"(₹|\brs\.?\s?\d|\binr\s?\d|\$\s?\d|\busd\s?\d)", re.IGNORECASE)
PROMO_RE = re.compile(
    r"(\d{1,2}\s?% off|\bsale\b|\bdiscount|\bcoupon|promo code|\bcashback\b|\bdeals?\b|"
    r"\boffers?\b|limited[- ]time|ends (tonight|today|soon)|last (chance|day)|free shipping|"
    r"shop now|buy now|\bsave (up to|\d)|\bflat \d|\bexclusive\b|early access|new arrivals?|\bbogo\b)",
    re.IGNORECASE,
)
SECURITY_RE = re.compile(
    r"\b(otp|one[- ]time password|verification code|security (alert|code)|sign[- ]?in|"
    r"new login|password (reset|changed)|2-step|two-factor|verify your)\b",
    re.IGNORECASE,
)
WORK_HINT_RE = re.compile(
    r"\b(interview|application (received|status|update)|offer letter|onboarding|meeting|"
    r"invitation:|updated invitation|assignment|deadline|resume|shortlisted|internship|"
    r"placement|timesheet|standup|sprint)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EmailSignals:
    sender: str
    subject: str = ""
    preview: str = ""
    sender_name: str | None = None
    labels: tuple[str, ...] = ()
    is_bulk: bool = False
    is_automated: bool = False
    is_starred: bool = False
    gmail_important: bool = False

    @property
    def sender_domain(self) -> str:
        return self.sender.rsplit("@", 1)[-1].lower() if "@" in self.sender else ""

    @property
    def text(self) -> str:
        return f"{self.subject} {self.preview}"


@dataclass
class ClassifierContext:
    user_email: str = ""
    contacted: set[str] = field(default_factory=set)
    sender_rules: dict[str, EmailCategory] = field(default_factory=dict)
    # sender -> (category, share of confident labels, number of confident labels)
    sender_history: dict[str, tuple[EmailCategory, float, int]] = field(default_factory=dict)

    @property
    def user_domain(self) -> str:
        return self.user_email.rsplit("@", 1)[-1].lower() if "@" in self.user_email else ""


@dataclass(frozen=True)
class Classification:
    category: EmailCategory
    confidence: float
    source: CategorySource
    reason: str


def domain_matches(domain: str, candidates: frozenset[str]) -> bool:
    if not domain:
        return False
    parts = domain.split(".")
    return any(".".join(parts[i:]) in candidates for i in range(len(parts) - 1))


def _rule_candidates(signals: EmailSignals, ctx: ClassifierContext) -> list[Classification]:
    rule = CategorySource.RULE
    labels = set(signals.labels)
    domain = signals.sender_domain
    text = signals.text
    gmail_promo = "CATEGORY_PROMOTIONS" in labels
    looks_promotional = signals.is_bulk and (gmail_promo or bool(PROMO_RE.search(signals.subject)))
    transactional = bool(FINANCE_TRANSACTION_RE.search(text))
    finance_domain = domain_matches(domain, FINANCE_DOMAINS)
    out: list[Classification] = []

    if finance_domain:
        if transactional and not looks_promotional:
            out.append(Classification(EmailCategory.FINANCE, 0.97, rule, "Transaction or statement from a bank / payment provider"))
        elif looks_promotional:
            out.append(Classification(EmailCategory.PROMOTIONS, 0.88, rule, "Marketing email from a bank / payment provider"))
        else:
            out.append(Classification(EmailCategory.FINANCE, 0.86, rule, "Sender is a bank / payment provider"))
    elif transactional and not looks_promotional:
        confidence = 0.85 if CURRENCY_RE.search(text) else 0.78
        out.append(Classification(EmailCategory.FINANCE, confidence, rule, "Mentions a payment, bill or statement"))

    if domain_matches(domain, SOCIAL_DOMAINS):
        out.append(Classification(EmailCategory.SOCIAL, 0.9, rule, "Sender is a social network"))

    if looks_promotional and not finance_domain:
        reason = "Bulk mail in Gmail's Promotions tab" if gmail_promo else "Bulk mail with promotional wording"
        out.append(Classification(EmailCategory.PROMOTIONS, 0.9 if gmail_promo else 0.84, rule, reason))

    personal_sender = (
        signals.sender in ctx.contacted and not signals.is_bulk and not signals.is_automated
    )
    if personal_sender:
        if domain in CONSUMER_DOMAINS:
            out.append(Classification(EmailCategory.PERSONAL, 0.88, rule, "A person you have emailed before"))
        elif ctx.user_domain and domain == ctx.user_domain and domain not in CONSUMER_DOMAINS:
            out.append(Classification(EmailCategory.WORK, 0.92, rule, "Colleague at your organization"))
        else:
            out.append(Classification(EmailCategory.WORK, 0.8, rule, "A professional contact you have emailed"))
    elif ctx.user_domain and domain == ctx.user_domain and domain not in CONSUMER_DOMAINS:
        out.append(Classification(EmailCategory.WORK, 0.85, rule, "From your organization's domain"))

    if signals.is_automated and not signals.is_bulk and SECURITY_RE.search(text) and not finance_domain:
        out.append(Classification(EmailCategory.UPDATES, 0.86, rule, "Automated account / security notification"))

    if WORK_HINT_RE.search(signals.subject) and not signals.is_bulk:
        out.append(Classification(EmailCategory.WORK, 0.7, rule, "Subject looks work or career related"))

    return out


def _gmail_label_candidate(signals: EmailSignals) -> Classification | None:
    gmail = CategorySource.GMAIL
    labels = set(signals.labels)
    if "CATEGORY_PROMOTIONS" in labels:
        return Classification(EmailCategory.PROMOTIONS, 0.85 if signals.is_bulk else 0.78, gmail, "Gmail Promotions tab")
    if "CATEGORY_SOCIAL" in labels or "CATEGORY_FORUMS" in labels:
        return Classification(EmailCategory.SOCIAL, 0.8, gmail, "Gmail Social / Forums tab")
    if "CATEGORY_UPDATES" in labels:
        automated = signals.is_bulk or signals.is_automated
        return Classification(EmailCategory.UPDATES, 0.78 if automated else 0.68, gmail, "Gmail Updates tab")
    if "CATEGORY_PERSONAL" in labels:
        return Classification(EmailCategory.PERSONAL, 0.5, gmail, "Gmail Primary tab")
    return None


def classify(signals: EmailSignals, ctx: ClassifierContext) -> Classification | None:
    """Best deterministic guess for an email, or None when there is no signal at all."""
    pinned = ctx.sender_rules.get(signals.sender)
    if pinned is not None:
        return Classification(pinned, 0.99, CategorySource.SENDER_RULE, "You filed this sender's emails here")

    candidates = _rule_candidates(signals, ctx)

    history = ctx.sender_history.get(signals.sender)
    if history is not None:
        category, share, count = history
        if count >= SENDER_HISTORY_MIN_EMAILS and share >= SENDER_HISTORY_MIN_SHARE:
            candidates.append(
                Classification(
                    category,
                    0.86,
                    CategorySource.SENDER_HISTORY,
                    f"{round(share * 100)}% of {count} emails from this sender are {category.value}",
                )
            )

    gmail = _gmail_label_candidate(signals)
    if gmail is not None:
        candidates.append(gmail)

    if not candidates:
        return None
    return max(candidates, key=lambda item: item.confidence)


def compute_priority(
    signals: EmailSignals,
    category: EmailCategory | None,
    ctx: ClassifierContext,
) -> int:
    """0-100 score; >= PRIORITY_THRESHOLD is shown as Important. Independent of category."""
    score = 30
    if signals.is_starred:
        score += 35
    if signals.gmail_important:
        score += 20
    if signals.sender in ctx.contacted and not signals.is_bulk:
        score += 25
    if category in (EmailCategory.PERSONAL, EmailCategory.WORK):
        score += 10
    finance_alert = category == EmailCategory.FINANCE and bool(FINANCE_TRANSACTION_RE.search(signals.text))
    if finance_alert:
        score += 10
    if signals.is_bulk:
        score -= 25
    if signals.is_automated and not finance_alert:
        score -= 15
    if category in (EmailCategory.PROMOTIONS, EmailCategory.SOCIAL):
        score -= 20
    return max(0, min(100, score))


def signals_from_fields(
    *,
    sender: str,
    subject: str | None,
    preview: str | None,
    sender_name: str | None = None,
    labels: str | list[str] | None = None,
    is_bulk: bool = False,
    is_automated: bool = False,
    is_starred: bool = False,
    is_important: bool = False,
) -> EmailSignals:
    return EmailSignals(
        sender=(sender or "").lower(),
        subject=subject or "",
        preview=(preview or "")[:600],
        sender_name=sender_name,
        labels=tuple(parse_label_ids(labels)),
        is_bulk=is_bulk,
        is_automated=is_automated,
        is_starred=is_starred,
        gmail_important=is_important,
    )
