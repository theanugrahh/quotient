from __future__ import annotations

from tests.conftest import BASE_URL, create_client_record


def test_create_and_fetch_a_client(auth_client) -> None:
    created = create_client_record(auth_client)
    assert created["name"] == "Acme Studio"
    assert created["archived"] is False

    fetched = auth_client.get(f"{BASE_URL}/clients/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["company"] == "Acme"


def test_client_list_is_paginated(auth_client) -> None:
    create_client_record(auth_client, "First")
    create_client_record(auth_client, "Second")

    response = auth_client.get(f"{BASE_URL}/clients", params={"page_size": 1})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["meta"]["total"] == 2
    assert body["meta"]["pages"] == 2


def test_client_search_filters_results(auth_client) -> None:
    create_client_record(auth_client, "Northwind")
    create_client_record(auth_client, "Southwind")

    response = auth_client.get(f"{BASE_URL}/clients", params={"q": "north"})
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


def test_client_update_changes_fields(auth_client) -> None:
    created = create_client_record(auth_client)
    response = auth_client.patch(
        f"{BASE_URL}/clients/{created['id']}",
        json={"name": "Acme Studios", "notes": "Prefers invoices on the 1st."},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Studios"


def test_archiving_hides_the_client(auth_client) -> None:
    created = create_client_record(auth_client)
    response = auth_client.delete(f"{BASE_URL}/clients/{created['id']}")
    assert response.status_code == 204

    listing = auth_client.get(f"{BASE_URL}/clients").json()
    assert listing["meta"]["total"] == 0


def test_clients_are_scoped_to_the_owner(auth_client, second_client) -> None:
    created = create_client_record(auth_client)

    assert second_client.get(f"{BASE_URL}/clients/{created['id']}").status_code == 404
    assert second_client.patch(f"{BASE_URL}/clients/{created['id']}", json={"name": "Hijacked"}).status_code == 404
    assert second_client.delete(f"{BASE_URL}/clients/{created['id']}").status_code == 404
    assert second_client.get(f"{BASE_URL}/clients").json()["meta"]["total"] == 0


def test_client_requires_authentication(client) -> None:
    response = client.get(f"{BASE_URL}/clients")
    assert response.status_code == 401
