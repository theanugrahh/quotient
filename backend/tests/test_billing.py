from __future__ import annotations

import json
import time

from app.config import settings
from app.payments.base import MockPaymentProvider
from tests.conftest import BASE_URL, create_client_record, create_invoice


def _signed_payload(**overrides) -> tuple[bytes, str]:
    provider = MockPaymentProvider(settings.mock_webhook_secret)
    body = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_mock_test",
                "user_id": "user-id",
                "plan": "pro",
                "amount_cents": 1900,
                "currency": "usd",
                "status": "paid",
            }
        },
    }
    body.update(overrides)
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    return payload, provider.sign(payload, int(time.time()))


def test_webhook_rejects_a_missing_signature(client) -> None:
    response = client.post(f"{BASE_URL}/webhooks/mock", content=b"{}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_signature"


def test_webhook_rejects_a_forged_signature(client) -> None:
    response = client.post(
        f"{BASE_URL}/webhooks/mock",
        content=b'{"id":"evt"}',
        headers={"X-Webhook-Signature": "1.deadbeef"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_signature"


def test_webhook_accepts_a_validly_signed_event(client) -> None:
    payload, signature = _signed_payload()
    response = client.post(
        f"{BASE_URL}/webhooks/mock",
        content=payload,
        headers={"X-Webhook-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] in {"no_matching_payment", "applied"}


def test_webhook_processing_is_idempotent(client) -> None:
    payload, signature = _signed_payload()
    first = client.post(
        f"{BASE_URL}/webhooks/mock",
        content=payload,
        headers={"X-Webhook-Signature": signature},
    )
    second = client.post(
        f"{BASE_URL}/webhooks/mock",
        content=payload,
        headers={"X-Webhook-Signature": signature},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_webhook_without_an_event_id_is_rejected(client) -> None:
    provider = MockPaymentProvider(settings.mock_webhook_secret)
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}).encode()
    signature = provider.sign(payload, int(time.time()))
    response = client.post(
        f"{BASE_URL}/webhooks/mock",
        content=payload,
        headers={"X-Webhook-Signature": signature},
    )
    assert response.status_code == 422


def test_two_different_payments_are_both_applied(auth_client) -> None:
    for _ in range(2):
        checkout = auth_client.post(f"{BASE_URL}/billing/checkout", json={"plan": "pro"})
        session_id = checkout.json()["session_id"]
        complete = auth_client.post(f"{BASE_URL}/billing/mock/checkout/{session_id}/complete")
        assert complete.json()["status"] == "applied"

    history = auth_client.get(f"{BASE_URL}/billing/payments").json()
    assert len(history) == 2
    assert all(entry["status"] == "paid" for entry in history)


def test_unknown_provider_is_rejected(client) -> None:
    response = client.post(f"{BASE_URL}/webhooks/nowhere", content=b"{}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_provider"


def test_checkout_upgrades_the_account_to_pro(auth_client) -> None:
    assert auth_client.get(f"{BASE_URL}/billing/plan").json()["current_plan"] == "free"

    checkout = auth_client.post(f"{BASE_URL}/billing/checkout", json={"plan": "pro"})
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    session_id = body["session_id"]
    assert body["url"] == f"/billing/mock/checkout/{session_id}"

    page = auth_client.get(f"{BASE_URL}/billing/mock/checkout/{session_id}")
    assert page.status_code == 200
    assert "sandbox checkout" in page.text

    complete = auth_client.post(f"{BASE_URL}/billing/mock/checkout/{session_id}/complete")
    assert complete.status_code == 200, complete.text

    assert auth_client.get(f"{BASE_URL}/billing/plan").json()["current_plan"] == "pro"
    assert auth_client.get(f"{BASE_URL}/auth/me").json()["plan"] == "pro"


def test_checkout_session_cannot_be_completed_by_another_account(auth_client, second_client) -> None:
    checkout = auth_client.post(f"{BASE_URL}/billing/checkout", json={"plan": "pro"})
    session_id = checkout.json()["session_id"]

    response = second_client.post(f"{BASE_URL}/billing/mock/checkout/{session_id}/complete")
    assert response.status_code == 403


def test_public_invoice_checkout_marks_the_invoice_paid(auth_client) -> None:
    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    auth_client.post(f"{BASE_URL}/invoices/{invoice['id']}/send")
    token = auth_client.get(f"{BASE_URL}/invoices/{invoice['id']}/share").json()["token"]

    checkout = auth_client.post(f"{BASE_URL}/public/invoices/{token}/checkout")
    assert checkout.status_code == 200, checkout.text
    session_id = checkout.json()["session_id"]

    complete = auth_client.post(f"{BASE_URL}/billing/mock/checkout/{session_id}/complete")
    assert complete.status_code == 200

    detail = auth_client.get(f"{BASE_URL}/invoices/{invoice['id']}").json()
    assert detail["status"] == "paid"
    assert detail["paid_at"] is not None


def test_payment_history_records_the_transaction(auth_client) -> None:
    checkout = auth_client.post(f"{BASE_URL}/billing/checkout", json={"plan": "pro"})
    auth_client.post(f"{BASE_URL}/billing/mock/checkout/{checkout.json()['session_id']}/complete")

    history = auth_client.get(f"{BASE_URL}/billing/payments").json()
    assert len(history) == 1
    assert history[0]["status"] == "paid"
    assert history[0]["amount_cents"] == 1900
