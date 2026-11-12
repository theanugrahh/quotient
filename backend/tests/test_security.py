from __future__ import annotations

import asyncio

from app.config import settings
from app.rate_limit import SlidingWindowLimiter
from tests.conftest import BASE_URL, prime_csrf


def test_csrf_token_is_required_for_mutations(auth_client) -> None:
    auth_client.headers.pop("X-CSRF-Token", None)
    response = auth_client.post(f"{BASE_URL}/clients", json={"name": "No Token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_missing"


def test_mismatched_csrf_token_is_rejected(auth_client) -> None:
    auth_client.headers["X-CSRF-Token"] = "not-the-right-token"
    response = auth_client.post(f"{BASE_URL}/clients", json={"name": "Bad Token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_invalid"


def test_security_headers_are_present(client) -> None:
    response = client.get(f"{BASE_URL}/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["permissions-policy"]


def test_responses_carry_a_request_id(client) -> None:
    response = client.get(f"{BASE_URL}/health")
    assert response.headers["x-request-id"]


def test_errors_use_a_consistent_envelope(client) -> None:
    response = client.get(f"{BASE_URL}/invoices/does-not-exist")
    body = response.json()
    assert set(body["error"]) >= {"code", "message", "request_id"}
    assert "Traceback" not in response.text
    assert "sqlalchemy" not in response.text.lower()


def test_oversized_request_bodies_are_rejected(auth_client) -> None:
    payload = {"name": "x" * 200, "notes": "y" * 9_000_000}
    response = auth_client.post(f"{BASE_URL}/clients", json=payload)
    assert response.status_code == 413


def test_unknown_routes_return_a_json_envelope(client) -> None:
    response = client.get(f"{BASE_URL}/definitely-not-here")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_sliding_window_limiter_blocks_after_the_limit() -> None:
    limiter = SlidingWindowLimiter(window_seconds=60)

    async def scenario() -> None:
        for _ in range(3):
            status = await limiter.hit("key", 3)
            assert status.allowed is True
        blocked = await limiter.hit("key", 3)
        assert blocked.allowed is False
        assert blocked.retry_after >= 1

    asyncio.run(scenario())


def test_rate_limit_is_enforced_on_authentication(client, monkeypatch) -> None:
    from app.rate_limit import limiter

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_auth", 3)
    limiter.reset()

    prime_csrf(client)
    for _ in range(3):
        response = client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "nobody@example.com", "password": "Str0ngPassw0rd!"},
        )
        assert response.status_code == 401

    blocked = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": "nobody@example.com", "password": "Str0ngPassw0rd!"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert "Retry-After" in blocked.headers
