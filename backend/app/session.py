from __future__ import annotations

from fastapi import Response

from app.config import settings
from app.security import create_csrf_token


def set_auth_cookies(response: Response, *, token: str, csrf_token: str, expires_at) -> None:
    max_age = max(0, int(expires_at.timestamp() - __import__("time").time()))
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=settings.cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(key=settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)


def ensure_csrf_cookie(response: Response, csrf_token: str | None = None) -> str:
    token = csrf_token or create_csrf_token()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    return token
