from __future__ import annotations

import json

import stripe

from app.config import settings
from app.payments.base import CheckoutSession, PaymentEvent, SignatureError


class StripePaymentProvider:
    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        stripe.api_key = secret_key
        self._webhook_secret = webhook_secret

    def create_checkout(
        self,
        *,
        user_id: str,
        user_email: str,
        plan: str,
        amount_cents: int,
        currency: str,
    ) -> CheckoutSession:
        if not settings.stripe_price_id:
            raise RuntimeError("STRIPE_PRICE_ID is required when the stripe provider is enabled.")

        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=user_email,
            line_items=[
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": amount_cents,
                        "product_data": {"name": f"Quotient {plan.title()} plan"},
                    },
                    "quantity": 1,
                }
            ],
            metadata={"user_id": user_id, "plan": plan},
            success_url=f"{settings.app_url}/billing?checkout=success",
            cancel_url=f"{settings.app_url}/billing?checkout=cancelled",
        )
        return CheckoutSession(session_id=session.id, path=session.url or "", provider=self.name)

    def verify_webhook(self, *, payload: bytes, signature: str | None) -> PaymentEvent:
        if not signature:
            raise SignatureError("Missing stripe-signature header.")
        try:
            event = stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
        except ValueError as exc:
            raise SignatureError("Malformed webhook payload.") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise SignatureError("Signature verification failed.") from exc

        obj = event["data"]["object"]
        metadata = obj.get("metadata", {}) or {}
        return PaymentEvent(
            event_id=event["id"],
            event_type=event["type"],
            provider_ref=obj.get("id", ""),
            user_id=metadata.get("user_id"),
            amount_cents=int(obj.get("amount_total") or 0),
            currency=str(obj.get("currency") or "usd"),
            plan=str(metadata.get("plan") or "pro"),
            status="paid" if event["type"] == "checkout.session.completed" else "ignored",
        )


def dump_payload(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")
