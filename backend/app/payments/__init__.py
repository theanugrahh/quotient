from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.payments.base import MockPaymentProvider, PaymentProvider
from app.payments.stripe import StripePaymentProvider


@lru_cache
def get_provider() -> PaymentProvider:
    if settings.payments_provider == "stripe":
        if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
            raise RuntimeError(
                "STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET are required when PAYMENTS_PROVIDER=stripe."
            )
        return StripePaymentProvider(settings.stripe_secret_key, settings.stripe_webhook_secret)
    return MockPaymentProvider(settings.mock_webhook_secret)


__all__ = ["MockPaymentProvider", "PaymentProvider", "StripePaymentProvider", "get_provider"]
