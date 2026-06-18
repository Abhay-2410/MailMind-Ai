REFRESH_COOKIE_NAME = "mailmind_refresh_token"
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7


def set_refresh_cookie(response, refresh_token: str, *, secure: bool) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=REFRESH_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
    )
