from __future__ import annotations

from tests.conftest import BASE_URL, create_client_record, create_invoice


def test_totals_are_computed_on_the_server(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])

    assert invoice["subtotal_cents"] == 160_000
    assert invoice["discount_cents"] == 8_000
    assert invoice["tax_cents"] == 15_200
    assert invoice["total_cents"] == 167_200
    assert [item["amount_cents"] for item in invoice["items"]] == [150_000, 10_000]


def test_client_supplied_totals_are_ignored(auth_client) -> None:
    client_record = create_client_record(auth_client)
    response = auth_client.post(
        f"{BASE_URL}/invoices",
        json={
            "client_id": client_record["id"],
            "items": [{"description": "Consulting", "quantity": "1", "unit_price_cents": 10000}],
            "total_cents": 1,
            "subtotal_cents": 1,
        },
    )
    assert response.status_code == 201
    assert response.json()["total_cents"] == 10_000


def test_invoice_numbers_increment_per_owner(auth_client, second_client) -> None:
    client_record = create_client_record(auth_client)
    assert create_invoice(auth_client, client_record["id"])["number"] == "INV-0001"
    assert create_invoice(auth_client, client_record["id"])["number"] == "INV-0002"

    other = create_client_record(second_client, "Other Client")
    assert create_invoice(second_client, other["id"])["number"] == "INV-0001"


def test_invoice_requires_at_least_one_line_item(auth_client) -> None:
    client_record = create_client_record(auth_client)
    response = auth_client.post(
        f"{BASE_URL}/invoices",
        json={"client_id": client_record["id"], "items": []},
    )
    assert response.status_code == 422


def test_invoice_rejects_unknown_client(auth_client) -> None:
    response = auth_client.post(
        f"{BASE_URL}/invoices",
        json={
            "client_id": "0" * 32,
            "items": [{"description": "Work", "quantity": "1", "unit_price_cents": 100}],
        },
    )
    assert response.status_code == 404


def test_invoice_rejects_negative_price(auth_client) -> None:
    client_record = create_client_record(auth_client)
    response = auth_client.post(
        f"{BASE_URL}/invoices",
        json={
            "client_id": client_record["id"],
            "items": [{"description": "Work", "quantity": "1", "unit_price_cents": -100}],
        },
    )
    assert response.status_code == 422


def test_status_workflow(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    assert invoice["status"] == "draft"

    sent = auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"

    paid = auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/mark-paid")
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"


def test_sent_invoices_cannot_be_edited(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/send")

    response = auth_client.patch(
        f"{BASE_URL}/invoices/{invoice['id']}",
        json={"notes": "Changed after sending"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invoice_not_editable"


def test_paid_invoices_cannot_be_deleted(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/mark-paid")

    response = auth_client.delete(f"{BASE_URL}/invoices/{invoice['id']}")
    assert response.status_code == 409


def test_draft_invoice_can_be_edited(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])

    response = auth_client.patch(
        f"{BASE_URL}/invoices/{invoice['id']}",
        json={
            "items": [{"description": "Revised scope", "quantity": "1", "unit_price_cents": 25000}],
            "tax_rate_bp": 0,
            "discount_bp": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["total_cents"] == 25_000


def test_invoice_list_filters_by_status(auth_client) -> None:
    client_record = create_client_record(auth_client)
    draft = create_invoice(auth_client, client_record["id"])
    create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{draft['id']}/send")

    drafts = auth_client.get(f"{BASE_URL}/invoices", params={"status": "draft"}).json()
    sent = auth_client.get(f"{BASE_URL}/invoices", params={"status": "sent"}).json()
    assert drafts["meta"]["total"] == 1
    assert sent["meta"]["total"] == 1


def test_dashboard_summary_counts_money(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/mark-paid")

    summary = auth_client.get(f"{BASE_URL}/invoices/stats/summary").json()
    assert summary["total_invoices"] == 1
    assert summary["paid_count"] == 1
    assert summary["collected_cents"] == 167_200
    assert summary["client_count"] == 1


def test_share_link_exposes_the_invoice_publicly(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/send")

    link = auth_client.get(f"{BASE_URL}/invoices/{invoice['id']}/share").json()
    assert link["token"]

    public = auth_client.get(f"{BASE_URL}/public/invoices/{link['token']}")
    assert public.status_code == 200
    body = public.json()
    assert body["number"] == invoice["number"]
    assert body["total_cents"] == 167_200
    assert body["studio_name"] == "Studio Owner"


def test_unknown_share_token_returns_not_found(client) -> None:
    response = client.get(f"{BASE_URL}/public/invoices/not-a-real-token")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "share_not_found"


def test_rotating_the_share_link_invalidates_the_old_token(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/send")
    first = auth_client.get(f"{BASE_URL}/invoices/{invoice['id']}/share").json()

    second = auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/share").json()
    assert second["token"] != first["token"]
    assert auth_client.get(f"{BASE_URL}/public/invoices/{first['token']}").status_code == 404
    assert auth_client.get(f"{BASE_URL}/public/invoices/{second['token']}").status_code == 200


def test_invoices_are_scoped_to_the_owner(auth_client, second_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])

    assert second_client.get(f"{BASE_URL}/invoices/{invoice['id']}").status_code == 404
    assert second_client.post(f"{BASE_URL}/invoices/{invoice['id']}/mark-paid").status_code == 404
    assert second_client.get(f"{BASE_URL}/invoices").json()["meta"]["total"] == 0
