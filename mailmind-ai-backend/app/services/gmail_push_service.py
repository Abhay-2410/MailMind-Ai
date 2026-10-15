"""Gmail push notifications: users.watch registration and Pub/Sub push verification.

Disabled unless GMAIL_PUBSUB_TOPIC is set. Setup (one-time, in Google Cloud):
  1. Create a Pub/Sub topic and grant gmail-api-push@system.gserviceaccount.com
     the Pub/Sub Publisher role on it.
  2. Create a push subscription to https://<backend>/api/v1/gmail/push with
     authentication enabled (service account + audience = GMAIL_PUSH_AUDIENCE).
"""

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.models.account import Account
from app.services.gmail_service import GmailService

logger = logging.getLogger(__name__)

WATCH_RENEW_BEFORE = timedelta(days=1)


def push_enabled(settings: Settings | None = None) -> bool:
    return bool((settings or get_settings()).GMAIL_PUBSUB_TOPIC)


async def ensure_gmail_watch(
    db: AsyncSession,
    account: Account,
    gmail: GmailService | None = None,
) -> bool:
    """Register / renew the mailbox watch when it is missing or about to expire."""
    settings = get_settings()
    if not push_enabled(settings):
        return False
    now = datetime.now(UTC)
    expires = account.gmail_watch_expires_at
    if expires is not None and expires - now > WATCH_RENEW_BEFORE:
        return False

    try:
        data = await (gmail or GmailService()).start_watch(
            account=account, db=db, topic_name=settings.GMAIL_PUBSUB_TOPIC
        )
    except AppError as exc:
        logger.warning("Gmail watch registration failed for %s: %s", account.email, exc.message)
        return False

    expiration_ms = data.get("expiration")
    if expiration_ms:
        account.gmail_watch_expires_at = datetime.fromtimestamp(int(expiration_ms) / 1000, tz=UTC)
    await db.commit()
    logger.info("Gmail watch active for %s until %s", account.email, account.gmail_watch_expires_at)
    return True


async def verify_push_token(authorization: str | None) -> dict[str, Any]:
    """Validate the OIDC bearer token Pub/Sub attaches to authenticated push requests."""
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("Missing push authentication", status_code=401)
    token = authorization.split(" ", 1)[1].strip()

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = await run_in_threadpool(
            id_token.verify_oauth2_token,
            token,
            google_requests.Request(),
            settings.GMAIL_PUSH_AUDIENCE or None,
        )
    except ValueError as exc:
        raise AppError("Invalid push token", status_code=401) from exc

    expected = settings.GMAIL_PUSH_SERVICE_ACCOUNT
    if expected and claims.get("email") != expected:
        raise AppError("Unexpected push sender", status_code=403)
    if expected and not claims.get("email_verified", False):
        raise AppError("Unverified push sender", status_code=403)
    return claims


def decode_push_payload(body: dict[str, Any]) -> tuple[str, str | None]:
    """Return (emailAddress, historyId) from a Pub/Sub push envelope."""
    message = body.get("message") or {}
    raw = message.get("data")
    if not raw:
        raise AppError("Empty push message", status_code=400)
    try:
        decoded = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("Malformed push message", status_code=400) from exc
    email_address = str(decoded.get("emailAddress") or "").strip().lower()
    if not email_address:
        raise AppError("Push message has no emailAddress", status_code=400)
    history_id = decoded.get("historyId")
    return email_address, str(history_id) if history_id is not None else None
