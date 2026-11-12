from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.config import settings


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    path: str
    provider: str


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    event_type: str
    provider_ref: str
    user_id: str | None
    amount_cents: int
    currency: str
    plan: str
    status: str


class PaymentProvider(Protocol):
    name: str

    def create_checkout(
        self,
        *,
        user_id: str,
        user_email: str,
        plan: str,
        amount_cents: int,
        currency: str,
    ) -> CheckoutSession: ...

    def verify_webhook(self, *, payload: bytes, signature: str | None) -> PaymentEvent: ...


class SignatureError(Exception):
    pass


def _parse_mock_signature(signature: str) -> tuple[int, bytes]:
    try:
        timestamp, digest = signature.split(".", 1)
        return int(timestamp), bytes.fromhex(digest)
    except (ValueError, TypeError) as exc:
        raise SignatureError("Malformed signature.") from exc


class MockPaymentProvider:
    """Local sandbox provider used for development and automated tests.

    It signs webhook payloads with an HMAC so the exact same verification code
    path is exercised in development and in production with Stripe.
    """

    name = "mock"

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def create_checkout(
        self,
        *,
        user_id: str,
        user_email: str,
        plan: str,
        amount_cents: int,
        currency: str,
    ) -> CheckoutSession:
        del user_id, user_email, plan, amount_cents, currency
        session_id = f"cs_mock_{secrets.token_urlsafe(16)}"
        return CheckoutSession(
            session_id=session_id,
            path=f"{settings.api_prefix}/billing/mock/checkout/{session_id}",
            provider=self.name,
        )

    def sign(self, payload: bytes, timestamp: int) -> str:
        digest = hmac.new(self._secret, f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return f"{timestamp}.{digest}"

    def verify_webhook(self, *, payload: bytes, signature: str | None) -> PaymentEvent:
        if not signature:
            raise SignatureError("Missing signature.")
        timestamp, digest = _parse_mock_signature(signature)
        expected = hmac.new(self._secret, f"{timestamp}.".encode() + payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, digest):
            raise SignatureError("Signature verification failed.")

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SignatureError("Payload is not valid JSON.") from exc

        data = json.loads(payload).get("data", {})
        data_obj = data.get("object", data) if isinstance(data, dict) else {}
        return PaymentEvent(
            event_id=str(data.get("id", "")),
            event_type=str(data.get("type", "")),
            provider_ref=str(data_obj.get("session_id") or data_obj.get("id", "")),
            user_id=data_obj.get("user_id"),
            amount_cents=int(Decimal(str(data_obj.get("amount_cents", 0)))),
            currency=str(data_obj.get("currency", "usd")),
            plan=str(data_obj.get("plan", "pro")),
            status=str(data_obj.get("status", "paid")),
        )
