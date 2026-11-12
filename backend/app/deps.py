from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import AuthenticationError, PermissionDenied, RateLimitError
from app.models import AuditEvent, User, UserRole
from app.rate_limit import limiter
from app.security import (
    CSRF_CLAIM,
    TokenError,
    constant_time_compare,
    decode_access_token,
)

DbSession = Annotated[Session, Depends(get_db)]


def get_client_ip(request: Request) -> str:
    if settings.trusted_proxy_hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            index = max(0, len(hops) - settings.trusted_proxy_hops)
            return hops[index]
    return request.client.host if request.client else "unknown"


def extract_token(request: Request) -> str | None:
    cookie_token = request.cookies.get(settings.cookie_name)
    if cookie_token:
        return cookie_token
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def get_current_user(request: Request, db: DbSession) -> User:
    token = extract_token(request)
    if not token:
        raise AuthenticationError("Sign in to continue.", code="missing_credentials")
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise AuthenticationError(str(exc), code="invalid_session") from exc

    user = db.get(User, payload.get("sub", ""))
    if user is None:
        raise AuthenticationError("Account no longer exists.", code="invalid_session")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.", code="account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def optional_current_user(request: Request, db: Session) -> User | None:
    """Resolve the signed in account when there is one, without raising."""
    try:
        return get_current_user(request, db)
    except AuthenticationError:
        return None


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise PermissionDenied("Administrator access required.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def verify_csrf(request: Request) -> None:
    """Double submit cookie check, cross-checked against the signed session token."""
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)

    if not cookie_token or not header_token:
        raise PermissionDenied("Missing CSRF token.", code="csrf_missing")
    if not constant_time_compare(cookie_token, header_token):
        raise PermissionDenied("Invalid CSRF token.", code="csrf_invalid")

    session_token = request.cookies.get(settings.cookie_name)
    if session_token:
        try:
            payload = decode_access_token(session_token)
        except TokenError as exc:
            raise PermissionDenied("Invalid CSRF token.", code="csrf_invalid") from exc
        claim = payload.get(CSRF_CLAIM, "")
        if not constant_time_compare(str(claim), header_token):
            raise PermissionDenied("Invalid CSRF token.", code="csrf_invalid")


CsrfGuard = Depends(verify_csrf)


def _resolve_limit(scope: str, override: int | None) -> int:
    if override is not None:
        return override
    attribute = f"rate_limit_{scope}"
    return int(getattr(settings, attribute, settings.rate_limit_default))


def _resolve_window(scope: str, override: int | None) -> int:
    if override is not None:
        return override
    attribute = f"rate_limit_{scope}_window_seconds"
    return int(getattr(settings, attribute, settings.rate_limit_window_seconds))


def rate_limited(scope: str, limit: int | None = None, window: int | None = None) -> Callable:
    """Build a dependency that enforces a sliding window limit for a route scope."""

    async def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        max_hits = _resolve_limit(scope, limit)
        window_seconds = _resolve_window(scope, window)
        key = f"{scope}:{get_client_ip(request)}"
        status = await limiter.hit(key, max_hits, window_seconds)
        if not status.allowed:
            raise RateLimitError(
                "Too many requests. Please slow down and try again shortly.",
                code="rate_limited",
                details=status.retry_after,
            )

    return dependency


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
        )
    )
