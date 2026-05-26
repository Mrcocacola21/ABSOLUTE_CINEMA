"""Factory for resolving configured payment provider adapters."""

from __future__ import annotations

from app.core.config import get_settings
from app.payments.providers.base import PaymentProvider
from app.payments.providers.fake import FakePaymentProvider
from app.schemas.payment import normalize_provider


def build_payment_provider(provider_name: str | None = None) -> PaymentProvider:
    """Return the configured payment provider adapter."""
    settings = get_settings()
    normalized_name = normalize_provider(provider_name or settings.payment_provider)

    if normalized_name == "fake":
        return FakePaymentProvider(
            webhook_secret=settings.payment_webhook_secret,
            checkout_base_url=settings.frontend_base_url,
        )

    raise ValueError(f"Unsupported payment provider '{normalized_name}'.")
