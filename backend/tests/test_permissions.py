from __future__ import annotations

from tests.conftest import BASE_URL, create_client_record, create_invoice


def test_admin_routes_reject_regular_users(auth_client) -> None:
    for path in ("/admin/users", "/admin/stats", "/admin/audit"):
        response = auth_client.get(f"{BASE_URL}{path}")
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "permission_denied"


def test_admin_routes_require_authentication(client) -> None:
    response = client.get(f"{BASE_URL}/admin/users")
    assert response.status_code == 401


def test_admin_can_list_users(admin_client) -> None:
    response = admin_client.get(f"{BASE_URL}/admin/users")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


def test_admin_can_promote_a_user(auth_client, admin_client) -> None:
    users = admin_client.get(f"{BASE_URL}/admin/users").json()["items"]
    target = users[0]

    response = admin_client.patch(f"{BASE_URL}/admin/users/{target['id']}/role", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_can_deactivate_a_user(auth_client, admin_client) -> None:
    users = admin_client.get(f"{BASE_URL}/admin/users").json()["items"]
    target = next(user for user in users if user["email"] == "owner@example.com")

    response = admin_client.post(f"{BASE_URL}/admin/users/{target['id']}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_cannot_deactivate_themselves(admin_client) -> None:
    users = admin_client.get(f"{BASE_URL}/admin/users").json()["items"]
    target = users[0]

    response = admin_client.post(f"{BASE_URL}/admin/users/{target['id']}/deactivate")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "self_deactivation"


def test_admin_cannot_demote_themselves(admin_client) -> None:
    users = admin_client.get(f"{BASE_URL}/admin/users").json()["items"]
    target = users[0]

    response = admin_client.patch(f"{BASE_URL}/admin/users/{target['id']}/role", json={"role": "user"})
    assert response.status_code == 422


def test_admin_stats_and_audit_log(admin_client, auth_client) -> None:
    client_record = create_client_record(auth_client)
    create_invoice(auth_client, client_record["id"])

    stats = admin_client.get(f"{BASE_URL}/admin/stats").json()
    assert stats["users"] == 2
    assert stats["invoices"] == 1
    assert stats["clients"] == 1

    audit = admin_client.get(f"{BASE_URL}/admin/audit").json()
    assert audit["meta"]["total"] > 0
    actions = [event["action"] for event in audit["items"]]
    assert "auth.register" in actions


def test_inactive_user_cannot_use_the_api(admin_client, auth_client) -> None:
    users = admin_client.get(f"{BASE_URL}/admin/users").json()["items"]
    target = next(user for user in users if user["email"] == "owner@example.com")
    admin_client.post(f"{BASE_URL}/admin/users/{target['id']}/deactivate")

    response = auth_client.get(f"{BASE_URL}/invoices")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "account_disabled"
