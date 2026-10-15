"""Golden-set evaluation for email categorization.

1. Export a stratified sample, then fill in the empty "label" column by hand:
     python -m app.cli.eval_categorization export --user you@gmail.com --per-category 25 > golden.csv
2. Score the current categories against your labels:
     python -m app.cli.eval_categorization evaluate --user you@gmail.com golden.csv
   (use "-" instead of a path to read the CSV from stdin)

Labels must be one of: work, personal, finance, promotions, social, updates.
"""

import argparse
import asyncio
import csv
import random
import sys
from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.email import Email
from app.models.user import User
from app.services.classifier import CONTENT_CATEGORIES

FIELDS = ["email_id", "sender", "subject", "preview", "predicted", "source", "confidence", "label"]
LABELS = [category.value for category in CONTENT_CATEGORIES]


async def _user(db, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        raise SystemExit(f"No user with email {email}")
    return user


async def _predictions(db, user_id: UUID) -> list[tuple]:
    result = await db.execute(
        select(
            Email.id,
            Email.sender,
            Email.subject,
            Email.preview,
            Category.category,
            Category.source,
            Category.confidence,
        )
        .outerjoin(Category, Category.email_id == Email.id)
        .where(Email.user_id == user_id)
    )
    return list(result.all())


async def export(user_email: str, per_category: int, seed: int) -> None:
    async with AsyncSessionLocal() as db:
        user = await _user(db, user_email)
        rows = await _predictions(db, user.id)

    buckets: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        buckets[row[4].value if row[4] else "uncategorized"].append(row)

    rng = random.Random(seed)
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
    writer.writeheader()
    for bucket in sorted(buckets):
        sample = rng.sample(buckets[bucket], min(per_category, len(buckets[bucket])))
        for email_id, sender, subject, preview, category, source, confidence in sample:
            writer.writerow(
                {
                    "email_id": str(email_id),
                    "sender": sender,
                    "subject": (subject or "")[:200],
                    "preview": (preview or "").replace("\n", " ")[:160],
                    "predicted": category.value if category else "",
                    "source": source or "",
                    "confidence": f"{confidence:.2f}" if confidence is not None else "",
                    "label": "",
                }
            )


def _read_labels(path: str) -> dict[UUID, str]:
    handle = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")  # noqa: SIM115
    try:
        labels: dict[UUID, str] = {}
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip().lower()
            if not label:
                continue
            if label not in LABELS:
                print(f"Skipping unknown label {label!r} for {row.get('email_id')}", file=sys.stderr)
                continue
            labels[UUID(row["email_id"])] = label
        return labels
    finally:
        if handle is not sys.stdin:
            handle.close()


async def evaluate(user_email: str, path: str) -> None:
    labels = _read_labels(path)
    if not labels:
        raise SystemExit("No labelled rows found (fill in the 'label' column).")

    async with AsyncSessionLocal() as db:
        user = await _user(db, user_email)
        rows = await _predictions(db, user.id)
    predicted = {
        email_id: (category.value if category else "none", source or "none")
        for email_id, _s, _subj, _p, category, source, _c in rows
    }

    pairs = [(gold, *predicted.get(email_id, ("missing", "none"))) for email_id, gold in labels.items()]
    total = len(pairs)
    correct = sum(1 for gold, pred, _ in pairs if gold == pred)
    print(f"Labelled emails: {total}   accuracy: {correct / total:.1%}\n")

    print(f"{'category':<12}{'precision':>10}{'recall':>10}{'f1':>8}{'support':>9}")
    f1_scores = []
    for label in LABELS:
        tp = sum(1 for gold, pred, _ in pairs if gold == label and pred == label)
        fp = sum(1 for gold, pred, _ in pairs if gold != label and pred == label)
        fn = sum(1 for gold, pred, _ in pairs if gold == label and pred != label)
        support = tp + fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if support:
            f1_scores.append(f1)
        print(f"{label:<12}{precision:>10.2f}{recall:>10.2f}{f1:>8.2f}{support:>9}")
    if f1_scores:
        print(f"{'macro f1':<12}{'':>20}{sum(f1_scores) / len(f1_scores):>8.2f}")

    print("\nAccuracy by source:")
    by_source: dict[str, Counter] = defaultdict(Counter)
    for gold, pred, source in pairs:
        by_source[source]["n"] += 1
        by_source[source]["ok"] += int(gold == pred)
    for source, counts in sorted(by_source.items(), key=lambda item: -item[1]["n"]):
        print(f"  {source:<16}{counts['ok'] / counts['n']:>7.1%}  ({counts['n']} emails)")

    predicted_labels = sorted({pred for _, pred, _ in pairs} | set(LABELS))
    print("\nConfusion matrix (rows = your label, columns = predicted):")
    print(" " * 12 + "".join(f"{name[:9]:>10}" for name in predicted_labels))
    matrix = Counter((gold, pred) for gold, pred, _ in pairs)
    for gold in LABELS:
        print(f"{gold:<12}" + "".join(f"{matrix[(gold, pred)]:>10}" for pred in predicted_labels))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    export_parser = sub.add_parser("export", help="write a stratified sample CSV to stdout")
    export_parser.add_argument("--user", required=True, help="MailMind user email")
    export_parser.add_argument("--per-category", type=int, default=25)
    export_parser.add_argument("--seed", type=int, default=7)

    evaluate_parser = sub.add_parser("evaluate", help="score current categories against a labelled CSV")
    evaluate_parser.add_argument("--user", required=True, help="MailMind user email")
    evaluate_parser.add_argument("path", help="labelled CSV path, or - for stdin")

    args = parser.parse_args()
    if args.command == "export":
        asyncio.run(export(args.user, args.per_category, args.seed))
    else:
        asyncio.run(evaluate(args.user, args.path))


if __name__ == "__main__":
    main()
