from __future__ import annotations

import json
import time

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import DbSession
from app.errors import ValidationError
from app.logging_config import get_logger
from app.payments.base import MockPaymentProvider, SignatureError
from app.payments.stripe import StripePaymentProvider
from app.services.payments import apply_payment_event, record_event

logger = get_logger("app.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _provider_for(name: str):
    if name == "mock":
        return MockPaymentProvider(settings.mock_webhook_secret)
    if name == "stripe":
        if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
            raise ValidationError("Stripe is not configured on this deployment.", code="provider_unavailable")
        return StripePaymentProvider(settings.stripe_secret_key, settings.stripe_webhook_secret)
    raise ValidationError("Unknown payment provider.", code="unknown_provider")


def process_webhook(*, provider: str, payload: bytes, signature: str | None, db: Session) -> dict:
    payment_provider = _provider_for(provider)
    try:
        event = payment_provider.verify_webhook(payload=payload, signature=signature)
    except SignatureError as exc:
        logger.warning("webhook_signature_rejected provider=%s", provider)
        raise ValidationError(str(exc), code="invalid_signature") from exc

    if not record_event(db, provider, event.event_id, event.event_type):
        return {"status": "duplicate", "event_id": event.event_id}

    outcome = apply_payment_event(db, event, provider)
    db.commit()
    logger.info("webhook_processed provider=%s event_type=%s outcome=%s", provider, event.event_type, outcome)
    return {"status": outcome, "event_id": event.event_id}


@router.post("/{provider}")
async def receive_webhook(request: Request, provider: str, db: DbSession) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature") or request.headers.get("x-webhook-signature")
    return process_webhook(provider=provider, payload=payload, signature=signature, db=db)


def build_mock_payload(
    *,
    event_id: str,
    session_id: str,
    user_id: str,
    plan: str,
    amount_cents: int,
    currency: str,
) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "user_id": user_id,
                    "plan": plan,
                    "amount_cents": amount_cents,
                    "currency": currency,
                    "status": "paid",
                }
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def sign_mock_payload(payload: bytes) -> str:
    provider = MockPaymentProvider(settings.mock_webhook_secret)
    return provider.sign(payload, int(time.time()))
