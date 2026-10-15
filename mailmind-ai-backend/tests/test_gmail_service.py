import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import GMAIL_REAUTH_CODE, AppError, GmailReauthRequired
from app.models.account import Account
from app.models.user import User
from app.services import gmail_service as gmail_module
from app.utils.encryption import encrypt_token
from app.services.gmail_service import (
    PERMISSION_MESSAGE,
    RATE_LIMITED_MESSAGE,
    GmailQuotaLimiter,
    GmailService,
    gmail_quota_cost,
)


def _gmail_error(status: int, reason: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}},
    )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(gmail_module.asyncio, "sleep", instant)


async def test_request_retries_rate_limited_403() -> None:
    responses = [
        _gmail_error(403, "userRateLimitExceeded"),
        _gmail_error(429, "rateLimitExceeded"),
        httpx.Response(200, json={"emailAddress": "user@example.com"}),
    ]
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return responses.pop(0)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        data = await GmailService()._request("GET", "profile", "token", client=client)

    assert data == {"emailAddress": "user@example.com"}
    assert calls == 3


async def test_request_persistent_rate_limit_is_429_not_permission_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _gmail_error(403, "userRateLimitExceeded")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AppError) as exc_info:
            await GmailService()._request("GET", "messages", "token", client=client)

    assert exc_info.value.status_code == 429
    assert exc_info.value.message == RATE_LIMITED_MESSAGE


async def test_request_insufficient_scope_is_permission_error_without_retry() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _gmail_error(403, "insufficientPermissions")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AppError) as exc_info:
            await GmailService()._request("GET", "messages", "token", client=client)

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == PERMISSION_MESSAGE
    assert calls == 1


def test_quota_costs_match_gmail_reference() -> None:
    assert gmail_quota_cost("GET", "messages/abc") == 5
    assert gmail_quota_cost("GET", "history") == 2
    assert gmail_quota_cost("GET", "labels/SPAM") == 1
    assert gmail_quota_cost("POST", "messages/batchDelete") == 50
    assert gmail_quota_cost("POST", "watch") == 100


async def test_quota_limiter_paces_requests_beyond_burst(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(gmail_module.asyncio, "sleep", fake_sleep)
    limiter = GmailQuotaLimiter(rate=100.0, burst=100.0, clock=lambda: now[0])

    await limiter.acquire("user", 100)
    assert slept == []
    await limiter.acquire("user", 50)
    assert sum(slept) == pytest.approx(0.5)
    await limiter.acquire("other-user", 100)
    assert sum(slept) == pytest.approx(0.5)


def _batch_part(index: int, status_line: str, body: dict) -> str:
    return (
        "--batch_resp\r\n"
        "Content-Type: application/http\r\n"
        f"Content-ID: <response-item-{index}>\r\n\r\n"
        f"HTTP/1.1 {status_line}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(body)}\r\n"
    )


def test_parse_batch_response_returns_throttled_ids_for_retry() -> None:
    message = {
        "id": "m0",
        "threadId": "t0",
        "labelIds": ["INBOX"],
        "payload": {"headers": [{"name": "From", "value": "a@example.com"}]},
    }
    raw = (
        _batch_part(0, "200 OK", message)
        + _batch_part(1, "429 Too Many Requests", {"error": {"code": 429}})
        + _batch_part(
            2,
            "403 Forbidden",
            {"error": {"code": 403, "errors": [{"reason": "rateLimitExceeded"}]}},
        )
        + _batch_part(3, "404 Not Found", {"error": {"code": 404}})
        + "--batch_resp--"
    )

    messages, retry_ids = GmailService()._parse_batch_response(
        raw, ["m0", "m1", "m2", "m3", "m4"], "batch_resp"
    )

    assert [m.gmail_id for m in messages] == ["m0"]
    # m4 had no response part at all, so it is retried as well; m3 (404) is not.
    assert sorted(retry_ids) == ["m1", "m2", "m4"]


async def _token_account(db_session: AsyncSession, suffix: str) -> Account:
    user = User(email=f"token-{suffix}@example.com", google_id=f"g-token-{suffix}", is_active=True)
    db_session.add(user)
    await db_session.flush()
    account = Account(
        user_id=user.id,
        email=user.email,
        access_token_encrypted=encrypt_token(f"old-token-{suffix}"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    return account


def _accept_only(token: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers["Authorization"] == f"Bearer {token}":
            return httpx.Response(200, json={"emailAddress": "user@example.com"})
        return httpx.Response(401, json={"error": {"code": 401, "message": "invalid credentials"}})

    return handler


async def test_request_json_recovers_from_revoked_but_unexpired_token(db_session: AsyncSession) -> None:
    """Regression: the 401 path used to re-enter the per-account lock and hang forever."""
    account = await _token_account(db_session, "recover")
    service = GmailService()
    refreshed: list[str] = []

    async def fake_refresh(refresh_token: str) -> dict:
        refreshed.append(refresh_token)
        return {"access_token": "new-token", "expires_in": 3600}

    service.refresh_access_token = fake_refresh  # type: ignore[method-assign]

    async with httpx.AsyncClient(transport=httpx.MockTransport(_accept_only("new-token"))) as client:
        data = await asyncio.wait_for(
            service.request_json("GET", "profile", account, db_session, client=client), timeout=5
        )

    assert data == {"emailAddress": "user@example.com"}
    assert refreshed == ["refresh-token"]
    # The rejected token is never reused, and a caller that saw the same 401 shares the refresh.
    token = await service.ensure_valid_access_token(
        account, db_session, force_refresh=True, rejected_token="old-token-recover"
    )
    assert token == "new-token"
    assert refreshed == ["refresh-token"]


async def test_request_json_dead_grant_requires_reconnect(db_session: AsyncSession) -> None:
    account = await _token_account(db_session, "dead")
    service = GmailService()

    async def fake_refresh(_refresh_token: str) -> dict:
        raise GmailReauthRequired()

    service.refresh_access_token = fake_refresh  # type: ignore[method-assign]

    async with httpx.AsyncClient(transport=httpx.MockTransport(_accept_only("never"))) as client:
        with pytest.raises(GmailReauthRequired) as exc_info:
            await asyncio.wait_for(
                service.request_json("GET", "profile", account, db_session, client=client), timeout=5
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == GMAIL_REAUTH_CODE
    await db_session.refresh(account)
    assert account.refresh_token_encrypted is None
    # Later calls fail fast without contacting Google.
    with pytest.raises(GmailReauthRequired):
        await service.ensure_valid_access_token(account, db_session)
