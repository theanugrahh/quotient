from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="quotient-tests-"))

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["UPLOADS_DIR"] = str(TEST_ROOT / "uploads")
os.environ["SECRET_KEY"] = "test-only-secret-key-please-do-not-use-in-production"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PAYMENTS_PROVIDER"] = "mock"
os.environ["MOCK_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.rate_limit import limiter  # noqa: E402

BASE_URL = "/api"
DEFAULT_PASSWORD = "Str0ngPassw0rd!"
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    limiter.reset()
    settings.rate_limit_enabled = False
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def prime_csrf(client: TestClient) -> str:
    response = client.get(f"{BASE_URL}/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = token
    return token


def register_user(
    client: TestClient,
    *,
    email: str = "owner@example.com",
    password: str = DEFAULT_PASSWORD,
    name: str = "Studio Owner",
) -> dict:
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    client.headers["X-CSRF-Token"] = payload["csrf_token"]
    return payload


@pytest.fixture
def auth_client(client):
    register_user(client)
    return client


@pytest.fixture
def second_client():
    """A second signed-in account used to verify tenant isolation."""
    with TestClient(app) as other:
        register_user(other, email="other@example.com", name="Other Studio")
        yield other


@pytest.fixture
def admin_client():
    """A signed-in account that holds the administrator role."""
    from app.database import SessionLocal
    from app.models import User, UserRole
    from app.security import hash_password

    with SessionLocal() as db:
        db.add(
            User(
                email="admin@example.com",
                name="Platform Admin",
                password_hash=hash_password(DEFAULT_PASSWORD),
                role=UserRole.ADMIN,
            )
        )
        db.commit()

    with TestClient(app) as admin:
        prime_csrf(admin)
        response = admin.post(
            f"{BASE_URL}/auth/login",
            json={"email": "admin@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 200, response.text
        admin.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield admin


def create_client_record(client: TestClient, name: str = "Acme Studio") -> dict:
    response = client.post(
        f"{BASE_URL}/clients",
        json={"name": name, "email": "billing@acme.example.com", "company": "Acme"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_invoice(client: TestClient, client_id: str, **overrides) -> dict:
    payload = {
        "client_id": client_id,
        "items": [
            {"description": "Design retainer", "quantity": "10", "unit_price_cents": 15000},
            {"description": "Extra revisions", "quantity": "2.5", "unit_price_cents": 4000},
        ],
        "currency": "usd",
        "tax_rate_bp": 1000,
        "discount_bp": 500,
        "notes": "Thanks for the work.",
    }
    payload.update(overrides)
    response = client.post(f"{BASE_URL}/invoices", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
