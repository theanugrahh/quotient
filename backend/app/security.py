from __future__ import annotations

import contextlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

ALGORITHM = "HS256"
CSRF_CLAIM = "csrf"
ROLE_CLAIM = "role"

_hasher = PasswordHasher(time_cost=2, memory_cost=64 * 1024, parallelism=2)


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return True


def dummy_verify() -> None:
    """Burn roughly the same time as a real verification to blunt user enumeration."""
    with contextlib.suppress(Exception):
        _hasher.verify(DUMMY_HASH, "not-a-real-password")


DUMMY_HASH = _hasher.hash("timing-equalizer-placeholder")


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def create_access_token(
    *,
    user_id: str,
    role: str,
    csrf_token: str,
    expires_minutes: int | None = None,
) -> tuple[str, datetime]:
    ttl = expires_minutes if expires_minutes is not None else settings.access_token_ttl_minutes
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl)
    payload: dict[str, Any] = {
        "sub": user_id,
        ROLE_CLAIM: role,
        CSRF_CLAIM: csrf_token,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.app_name,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            issuer=settings.app_name,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Session expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid session token.") from exc


def generate_share_token() -> str:
    return secrets.token_urlsafe(32)


def password_problems(password: str) -> list[str]:
    problems: list[str] = []
    if len(password) < 10:
        problems.append("Password must be at least 10 characters long.")
    if len(password) > 128:
        problems.append("Password must be 128 characters or fewer.")
    if not any(char.isalpha() for char in password):
        problems.append("Password must contain at least one letter.")
    if not any(char.isdigit() for char in password):
        problems.append("Password must contain at least one number.")
    if password.lower() in {"password123", "qwerty12345", "administrator"}:
        problems.append("Password is too common.")
    return problems
