"""Deterministic fake payment provider adapter."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from app.core.constants import PaymentStatuses, RefundStatuses
from app.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderPaymentCancelRequest,
    ProviderPaymentCreateRequest,
    ProviderPaymentCreateResult,
    ProviderPaymentStatusRequest,
    ProviderPaymentStatusResult,
    ProviderRefundRequest,
    ProviderRefundResult,
    ProviderWebhookEvent,
)


class FakePaymentProvider(PaymentProvider):
    """Sandbox-ready provider that normalizes fake raw statuses into domain statuses."""

    RAW_PAYMENT_STATUS_TO_DOMAIN: dict[str, str] = {
        "created": PaymentStatuses.CREATED,
        "authorized": PaymentStatuses.PENDING,
        "action_required": PaymentStatuses.REQUIRES_ACTION,
        "paid": PaymentStatuses.SUCCEEDED,
        "declined": PaymentStatuses.FAILED,
        "voided": PaymentStatuses.CANCELLED,
        "expired": PaymentStatuses.EXPIRED,
        "refunded": PaymentStatuses.REFUNDED,
        "partially_refunded": PaymentStatuses.PARTIALLY_REFUNDED,
    }
    RAW_REFUND_STATUS_TO_DOMAIN: dict[str, str] = {
        "refund_created": RefundStatuses.CREATED,
        "refund_pending": RefundStatuses.PENDING,
        "refund_settled": RefundStatuses.SUCCEEDED,
        "refund_failed": RefundStatuses.FAILED,
        "refund_cancelled": RefundStatuses.CANCELLED,
    }

    def __init__(
        self,
        *,
        default_create_raw_status: str = "authorized",
        default_refund_raw_status: str = "refund_settled",
        webhook_secret: str = "fake-webhook-secret",
    ) -> None:
        self.default_create_raw_status = default_create_raw_status
        self.default_refund_raw_status = default_refund_raw_status
        self.webhook_secret = webhook_secret
        self._payment_statuses: dict[str, str] = {}
        self._payment_amounts: dict[str, int] = {}
        self._payment_currencies: dict[str, str] = {}
        self._refund_statuses: dict[str, str] = {}

    @property
    def name(self) -> str:
        """Return the fake provider identifier."""
        return "fake"

    async def create_payment(
        self,
        request: ProviderPaymentCreateRequest,
    ) -> ProviderPaymentCreateResult:
        """Return a stable fake provider payment reference."""
        provider_payment_id = f"fake-pay-{request.payment_id}"
        provider_attempt_id = f"fake-attempt-{request.payment_id}"
        raw_status = self._metadata_status(request.metadata, default=self.default_create_raw_status)
        status = self._map_payment_status(raw_status)
        self._payment_statuses[provider_payment_id] = raw_status
        self._payment_amounts[provider_payment_id] = request.amount_minor
        self._payment_currencies[provider_payment_id] = request.currency

        return ProviderPaymentCreateResult(
            provider=self.name,
            provider_payment_id=provider_payment_id,
            provider_attempt_id=provider_attempt_id,
            status=status,
            amount_minor=request.amount_minor,
            currency=request.currency,
            redirect_url=f"https://payments.example.test/fake/{provider_payment_id}",
            client_payload={
                "mode": "fake_redirect",
                "payment_reference": provider_payment_id,
            },
            failure_code="fake_declined" if status == PaymentStatuses.FAILED else None,
            failure_message="Fake provider declined the payment." if status == PaymentStatuses.FAILED else None,
            safe_metadata={
                "raw_status": raw_status,
                "provider_mode": "fake",
            },
        )

    async def get_payment_status(
        self,
        request: ProviderPaymentStatusRequest,
    ) -> ProviderPaymentStatusResult:
        """Return the stored fake status or the default status for unknown references."""
        raw_status = self._payment_statuses.get(
            request.provider_payment_id,
            self.default_create_raw_status,
        )
        status = self._map_payment_status(raw_status)
        amount_minor = self._payment_amounts.get(
            request.provider_payment_id,
            request.expected_amount_minor or 1,
        )
        currency = self._payment_currencies.get(
            request.provider_payment_id,
            request.expected_currency or "UAH",
        )
        return ProviderPaymentStatusResult(
            provider=self.name,
            provider_payment_id=request.provider_payment_id,
            provider_attempt_id=None,
            status=status,
            amount_minor=amount_minor,
            currency=currency,
            failure_code="fake_declined" if status == PaymentStatuses.FAILED else None,
            failure_message="Fake provider declined the payment." if status == PaymentStatuses.FAILED else None,
            safe_metadata={
                "raw_status": raw_status,
                "provider_mode": "fake",
            },
        )

    async def cancel_payment(
        self,
        request: ProviderPaymentCancelRequest,
    ) -> ProviderPaymentStatusResult:
        """Mark the fake payment as voided."""
        raw_status = "voided"
        self._payment_statuses[request.provider_payment_id] = raw_status
        amount_minor = self._payment_amounts.get(
            request.provider_payment_id,
            request.expected_amount_minor or 1,
        )
        currency = self._payment_currencies.get(
            request.provider_payment_id,
            request.expected_currency or "UAH",
        )
        return ProviderPaymentStatusResult(
            provider=self.name,
            provider_payment_id=request.provider_payment_id,
            provider_attempt_id=None,
            status=self._map_payment_status(raw_status),
            amount_minor=amount_minor,
            currency=currency,
            safe_metadata={
                "raw_status": raw_status,
                "reason": request.reason,
                "provider_mode": "fake",
            },
        )

    async def refund_payment(
        self,
        request: ProviderRefundRequest,
    ) -> ProviderRefundResult:
        """Return a stable fake provider refund reference."""
        provider_refund_id = f"fake-refund-{request.refund_id}"
        raw_status = self._metadata_status(request.metadata, default=self.default_refund_raw_status)
        status = self._map_refund_status(raw_status)
        self._refund_statuses[provider_refund_id] = raw_status

        return ProviderRefundResult(
            provider=self.name,
            provider_refund_id=provider_refund_id,
            status=status,
            amount_minor=request.amount_minor,
            currency=request.currency,
            failure_code="fake_refund_failed" if status == RefundStatuses.FAILED else None,
            failure_message="Fake provider failed the refund." if status == RefundStatuses.FAILED else None,
            safe_metadata={
                "raw_status": raw_status,
                "provider_mode": "fake",
            },
        )

    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Verify the fake HMAC-SHA256 webhook signature."""
        signature = self._header(headers, "x-fake-payment-signature")
        if not signature:
            raise PaymentProviderError("Missing fake webhook signature.", code="invalid_signature")

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PaymentProviderError("Invalid fake webhook signature.", code="invalid_signature")

    async def parse_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str] | None = None,
    ) -> ProviderWebhookEvent:
        """Normalize a fake webhook payload into the shared webhook contract."""
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PaymentProviderError("Malformed fake webhook payload.", code="invalid_webhook") from exc
        if not isinstance(payload, dict):
            raise PaymentProviderError("Fake webhook payload must be an object.", code="invalid_webhook")

        event_type = str(payload.get("event_type") or payload.get("type") or "fake.event")
        event_id = payload.get("event_id") or payload.get("id")
        payment_payload = payload.get("payment")
        refund_payload = payload.get("refund")

        payment = self._parse_payment_webhook(payment_payload) if isinstance(payment_payload, dict) else None
        refund = self._parse_refund_webhook(refund_payload) if isinstance(refund_payload, dict) else None

        return ProviderWebhookEvent(
            provider=self.name,
            event_id=str(event_id) if event_id else None,
            event_type=event_type,
            occurred_at=str(payload["occurred_at"]) if payload.get("occurred_at") else None,
            payment=payment,
            refund=refund,
            safe_metadata={
                "verified_header_present": bool(headers),
            },
        )

    def _parse_payment_webhook(self, payload: dict[str, Any]) -> ProviderPaymentStatusResult:
        raw_status = str(payload.get("status") or self.default_create_raw_status)
        status = self._map_payment_status(raw_status)
        provider_payment_id = str(payload.get("provider_payment_id") or payload.get("id") or "")
        if not provider_payment_id:
            raise PaymentProviderError("Fake payment webhook is missing a payment id.", code="invalid_webhook")

        return ProviderPaymentStatusResult(
            provider=self.name,
            provider_payment_id=provider_payment_id,
            provider_attempt_id=None,
            status=status,
            amount_minor=int(payload.get("amount_minor") or 1),
            currency=str(payload.get("currency") or "UAH"),
            failure_code="fake_declined" if status == PaymentStatuses.FAILED else None,
            failure_message="Fake provider declined the payment." if status == PaymentStatuses.FAILED else None,
            safe_metadata={
                "raw_status": raw_status,
                "provider_mode": "fake",
            },
        )

    def _parse_refund_webhook(self, payload: dict[str, Any]) -> ProviderRefundResult:
        raw_status = str(payload.get("status") or self.default_refund_raw_status)
        status = self._map_refund_status(raw_status)
        provider_refund_id = str(payload.get("provider_refund_id") or payload.get("id") or "")
        if not provider_refund_id:
            raise PaymentProviderError("Fake refund webhook is missing a refund id.", code="invalid_webhook")

        return ProviderRefundResult(
            provider=self.name,
            provider_refund_id=provider_refund_id,
            status=status,
            amount_minor=int(payload.get("amount_minor") or 1),
            currency=str(payload.get("currency") or "UAH"),
            failure_code="fake_refund_failed" if status == RefundStatuses.FAILED else None,
            failure_message="Fake provider failed the refund." if status == RefundStatuses.FAILED else None,
            safe_metadata={
                "raw_status": raw_status,
                "provider_mode": "fake",
            },
        )

    def _map_payment_status(self, raw_status: str) -> str:
        normalized = raw_status.strip().lower()
        try:
            return self.RAW_PAYMENT_STATUS_TO_DOMAIN[normalized]
        except KeyError as exc:
            raise PaymentProviderError(
                f"Fake provider returned unsupported payment status '{raw_status}'.",
                code="unsupported_payment_status",
                safe_metadata={"raw_status": raw_status},
            ) from exc

    def _map_refund_status(self, raw_status: str) -> str:
        normalized = raw_status.strip().lower()
        try:
            return self.RAW_REFUND_STATUS_TO_DOMAIN[normalized]
        except KeyError as exc:
            raise PaymentProviderError(
                f"Fake provider returned unsupported refund status '{raw_status}'.",
                code="unsupported_refund_status",
                safe_metadata={"raw_status": raw_status},
            ) from exc

    def _metadata_status(self, metadata: dict[str, Any] | None, *, default: str) -> str:
        if metadata is None:
            return default
        return str(metadata.get("fake_raw_status") or default)

    def _header(self, headers: dict[str, str] | None, key: str) -> str | None:
        if not headers:
            return None
        normalized_key = key.lower()
        for header_key, header_value in headers.items():
            if header_key.lower() == normalized_key:
                return header_value
        return None
