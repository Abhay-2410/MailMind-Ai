REFRESH_COOKIE_NAME = "mailmind_refresh_token"
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7


def set_refresh_cookie(response, refresh_token: str, *, secure: bool) -> None:
    # Cross-origin SPA (e.g. Vercel) needs SameSite=None + Secure so the
    # browser includes the HttpOnly refresh cookie on credentialed fetches.
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        max_age=REFRESH_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response, *, secure: bool = False) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        secure=secure,
        samesite="none" if secure else "lax",
    )
