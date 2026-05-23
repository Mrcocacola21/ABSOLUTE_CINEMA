"""Tests for payment provider contracts and resolution."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.core.config import Settings
from app.core.constants import PaymentStatuses, RefundStatuses
from app.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderPaymentCreateRequest,
    ProviderRefundRequest,
)
from app.payments.providers.factory import build_payment_provider
from app.payments.providers.fake import FakePaymentProvider


def sign_fake_payload(payload: dict[str, object], *, secret: str = "fake-webhook-secret") -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return raw_body, signature


def build_create_request() -> ProviderPaymentCreateRequest:
    return ProviderPaymentCreateRequest(
        payment_id="payment-1",
        order_id="order-1",
        external_order_reference="order-1",
        user_id="user-1",
        amount_minor=12345,
        currency="uah",
        idempotency_key="idem-12345",
        metadata={"flow": "provider-test"},
    )


@pytest.mark.asyncio
async def test_fake_provider_implements_contract_and_normalizes_payment_creation() -> None:
    provider: PaymentProvider = FakePaymentProvider(default_create_raw_status="paid")

    result = await provider.create_payment(build_create_request())

    assert isinstance(provider, PaymentProvider)
    assert result.provider == "fake"
    assert result.provider_payment_id == "fake-pay-payment-1"
    assert result.provider_attempt_id == "fake-attempt-payment-1"
    assert result.status == PaymentStatuses.SUCCEEDED
    assert result.amount_minor == 12345
    assert result.currency == "UAH"
    assert result.safe_metadata == {"raw_status": "paid", "provider_mode": "fake"}


@pytest.mark.asyncio
async def test_fake_provider_maps_provider_statuses_and_rejects_unknown_statuses() -> None:
    provider = FakePaymentProvider(default_create_raw_status="action_required")

    result = await provider.create_payment(build_create_request())
    assert result.status == PaymentStatuses.REQUIRES_ACTION
    expired_provider = FakePaymentProvider(default_create_raw_status="expired")
    expired = await expired_provider.create_payment(build_create_request())
    assert expired.status == PaymentStatuses.EXPIRED

    broken_provider = FakePaymentProvider(default_create_raw_status="settled_some_new_way")
    with pytest.raises(PaymentProviderError, match="unsupported payment status"):
        await broken_provider.create_payment(build_create_request())


@pytest.mark.asyncio
async def test_fake_provider_refund_contract_returns_normalized_result() -> None:
    provider = FakePaymentProvider(default_refund_raw_status="refund_settled")

    result = await provider.refund_payment(
        ProviderRefundRequest(
            refund_id="refund-1",
            payment_id="payment-1",
            provider_payment_id="fake-pay-payment-1",
            amount_minor=5000,
            currency="uah",
            reason="customer_request",
            idempotency_key="refund-1-idem",
        )
    )

    assert result.provider == "fake"
    assert result.provider_refund_id == "fake-refund-refund-1"
    assert result.status == RefundStatuses.SUCCEEDED
    assert result.amount_minor == 5000
    assert result.currency == "UAH"


@pytest.mark.asyncio
async def test_fake_provider_parses_webhook_into_provider_neutral_event() -> None:
    provider = FakePaymentProvider()
    raw_body, signature = sign_fake_payload(
        {
            "event_id": "evt-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "action_required",
                "amount_minor": 12345,
                "currency": "uah",
            },
        }
    )

    await provider.verify_webhook_signature(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    event = await provider.parse_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert event.provider == "fake"
    assert event.event_id == "evt-1"
    assert event.event_type == "payment.updated"
    assert event.payment is not None
    assert event.payment.status == PaymentStatuses.REQUIRES_ACTION
    assert event.payment.currency == "UAH"
    assert event.safe_metadata == {"verified_header_present": True}


@pytest.mark.asyncio
async def test_fake_provider_rejects_invalid_webhook_signature() -> None:
    provider = FakePaymentProvider()
    raw_body, _ = sign_fake_payload({"event_id": "evt-1"})

    with pytest.raises(PaymentProviderError, match="Missing fake webhook signature"):
        await provider.verify_webhook_signature(
            raw_body=raw_body,
            headers={},
        )
    with pytest.raises(PaymentProviderError, match="Invalid fake webhook signature"):
        await provider.verify_webhook_signature(
            raw_body=raw_body,
            headers={"x-fake-payment-signature": "bad"},
        )


@pytest.mark.asyncio
async def test_fake_provider_rejects_malformed_and_incomplete_webhook_payloads() -> None:
    provider = FakePaymentProvider()
    raw_body = b'["not", "an", "object"]'
    signature = hmac.new(b"fake-webhook-secret", raw_body, hashlib.sha256).hexdigest()

    with pytest.raises(PaymentProviderError, match="must be an object"):
        await provider.parse_webhook(
            raw_body=raw_body,
            headers={"x-fake-payment-signature": signature},
        )

    missing_payment_id_body, missing_payment_id_signature = sign_fake_payload(
        {
            "event_id": "evt-missing-payment-id",
            "event_type": "payment.updated",
            "payment": {"status": "paid", "amount_minor": 12345, "currency": "UAH"},
        }
    )
    with pytest.raises(PaymentProviderError, match="missing a payment id"):
        await provider.parse_webhook(
            raw_body=missing_payment_id_body,
            headers={"x-fake-payment-signature": missing_payment_id_signature},
        )


def test_payment_provider_factory_resolves_configured_fake_provider_and_rejects_unknown() -> None:
    provider = build_payment_provider("FAKE")

    assert isinstance(provider, FakePaymentProvider)
    assert provider.name == "fake"

    with pytest.raises(ValueError, match="Unsupported payment provider 'unknown'"):
        build_payment_provider("unknown")


def test_settings_normalizes_payment_provider_name() -> None:
    settings = Settings(payment_provider="FAKE")

    assert settings.payment_provider == "fake"
