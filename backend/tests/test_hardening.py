from __future__ import annotations

from tests.conftest import BASE_URL, DEFAULT_PASSWORD, TINY_PNG, create_client_record, prime_csrf


def test_client_can_be_created_without_an_email(auth_client) -> None:
    response = auth_client.post(f"{BASE_URL}/clients", json={"name": "Cash Only Ltd"})
    assert response.status_code == 201, response.text
    assert response.json()["email"] is None


def test_client_email_can_be_cleared(auth_client) -> None:
    created = create_client_record(auth_client)
    response = auth_client.patch(f"{BASE_URL}/clients/{created['id']}", json={"email": ""})
    assert response.status_code == 200
    assert response.json()["email"] is None


def test_session_token_cannot_be_forged(auth_client) -> None:
    auth_client.cookies.set("quotient_session", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.")
    response = auth_client.get(f"{BASE_URL}/admin/users")
    assert response.status_code == 401


def test_garbage_session_token_is_rejected(auth_client) -> None:
    auth_client.cookies.set("quotient_session", "not.a.jwt")
    assert auth_client.get(f"{BASE_URL}/invoices").status_code == 401


def test_inactive_account_cannot_use_a_valid_token(auth_client, admin_client) -> None:
    users = admin_client.get(f"{BASE_URL}/admin/users").json()["items"]
    target = next(user for user in users if user["email"] == "owner@example.com")
    admin_client.post(f"{BASE_URL}/admin/users/{target['id']}/deactivate")

    assert auth_client.get(f"{BASE_URL}/invoices").status_code == 401


def test_unknown_fields_are_ignored_on_registration(client) -> None:
    prime_csrf(client)
    response = client.post(
        f"{BASE_URL}/auth/register",
        json={
            "name": "Escalate",
            "email": "escalate@example.com",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
            "plan": "pro",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["role"] == "user"
    assert response.json()["user"]["plan"] == "free"


def test_sql_metacharacters_in_a_search_term_are_treated_as_text(auth_client) -> None:
    create_client_record(auth_client, "Northwind")
    response = auth_client.get(f"{BASE_URL}/clients", params={"q": "' OR 1=1--"})
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 0


def test_malformed_json_is_rejected(auth_client) -> None:
    response = auth_client.post(
        f"{BASE_URL}/clients",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_a_json_array_is_not_accepted_where_an_object_is_expected(auth_client) -> None:
    response = auth_client.post(
        f"{BASE_URL}/clients",
        content=b"[]",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_oversized_string_fields_are_rejected(auth_client) -> None:
    response = auth_client.post(f"{BASE_URL}/clients", json={"name": "x" * 5000})
    assert response.status_code == 422


def test_php_and_svg_uploads_are_refused(auth_client) -> None:
    import io

    for name, payload, content_type in (
        ("shell.php", b"<?php system($_GET['c']); ?>", "application/x-php"),
        ("avatar.svg", b"<svg onload=alert(1)>", "image/svg+xml"),
    ):
        response = auth_client.post(
            f"{BASE_URL}/files/upload",
            files={"file": (name, io.BytesIO(payload), content_type)},
        )
        assert response.status_code == 415, name


def test_share_token_cannot_be_guessed(auth_client) -> None:
    response = auth_client.get(f"{BASE_URL}/public/invoices/abcdefghijklmnopqrstuvwxyz")
    assert response.status_code == 404


def test_tiny_png_fixture_is_a_real_png() -> None:
    assert TINY_PNG.startswith(b"\x89PNG\r\n\x1a\n")
