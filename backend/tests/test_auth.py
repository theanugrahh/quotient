from __future__ import annotations

from tests.conftest import BASE_URL, DEFAULT_PASSWORD, prime_csrf, register_user


def test_register_creates_an_account_and_session(client) -> None:
    payload = register_user(client, email="studio@example.com")
    assert payload["user"]["email"] == "studio@example.com"
    assert payload["user"]["role"] == "user"
    assert payload["user"]["plan"] == "free"
    assert payload["csrf_token"]


def test_register_rejects_duplicate_email(client) -> None:
    register_user(client, email="studio@example.com")
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/register",
        json={"name": "Copy", "email": "studio@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_register_rejects_weak_password(client) -> None:
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/register",
        json={"name": "Weak", "email": "weak@example.com", "password": "allletters"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"


def test_register_validates_email_format(client) -> None:
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/register",
        json={"name": "Bad", "email": "not-an-email", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_with_valid_credentials(client) -> None:
    register_user(client, email="studio@example.com")
    client.cookies.clear()
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": "studio@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "studio@example.com"


def test_login_rejects_wrong_password(client) -> None:
    register_user(client, email="studio@example.com")
    client.cookies.clear()
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": "studio@example.com", "password": "Wr0ngPassw0rd!"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_for_unknown_account_is_indistinguishable(client) -> None:
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_a_session(client) -> None:
    response = client.get(f"{BASE_URL}/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_credentials"


def test_me_returns_the_signed_in_account(auth_client) -> None:
    response = auth_client.get(f"{BASE_URL}/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_logout_clears_the_session(auth_client) -> None:
    response = auth_client.post(f"{BASE_URL}/auth/logout")
    assert response.status_code == 204
    assert auth_client.get(f"{BASE_URL}/auth/me").status_code == 401


def test_password_change_requires_the_current_password(auth_client) -> None:
    response = auth_client.post(
        f"{BASE_URL}/auth/password",
        json={"current_password": "Wr0ngPassw0rd!", "new_password": "An0therPassw0rd!"},
    )
    assert response.status_code == 401


def test_password_change_updates_the_password(auth_client) -> None:
    response = auth_client.post(
        f"{BASE_URL}/auth/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "An0therPassw0rd!"},
    )
    assert response.status_code == 204

    auth_client.cookies.clear()
    prime_csrf(auth_client)
    login = auth_client.post(
        f"{BASE_URL}/auth/login",
        json={"email": "owner@example.com", "password": "An0therPassw0rd!"},
    )
    assert login.status_code == 200


def test_deactivated_account_cannot_sign_in(client) -> None:
    register_user(client, email="studio@example.com")
    client.cookies.clear()
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": "studio@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
