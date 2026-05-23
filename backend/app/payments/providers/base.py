"""Provider-neutral payment provider contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import Field, field_validator

from app.core.constants import PAYMENT_STATUS_VALUES, REFUND_STATUS_VALUES
from app.schemas.common import BaseSchema
from app.schemas.payment import normalize_currency, normalize_provider, validate_safe_snapshot


class PaymentProviderError(Exception):
    """Raised when a provider adapter cannot complete an operation."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "payment_provider_error",
        safe_metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.safe_metadata = validate_safe_snapshot(safe_metadata, field_name="safe_metadata")


class ProviderPaymentCreateRequest(BaseSchema):
    """Provider-neutral request to create or initiate a provider payment."""

    payment_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    external_order_reference: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1)
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=8, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None
    return_url: str | None = Field(default=None, max_length=2000)
    cancel_url: str | None = Field(default=None, max_length=2000)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="metadata")


class ProviderPaymentStatusRequest(BaseSchema):
    """Provider-neutral request to fetch a provider payment status."""

    payment_id: str = Field(min_length=1)
    provider_payment_id: str = Field(min_length=1, max_length=255)
    expected_amount_minor: int | None = Field(default=None, gt=0)
    expected_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("expected_currency")
    @classmethod
    def validate_expected_currency(cls, value: str | None) -> str | None:
        return normalize_currency(value) if value is not None else None


class ProviderPaymentCancelRequest(BaseSchema):
    """Provider-neutral request to cancel a provider payment."""

    payment_id: str = Field(min_length=1)
    provider_payment_id: str = Field(min_length=1, max_length=255)
    expected_amount_minor: int | None = Field(default=None, gt=0)
    expected_currency: str | None = Field(default=None, min_length=3, max_length=3)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("expected_currency")
    @classmethod
    def validate_expected_currency(cls, value: str | None) -> str | None:
        return normalize_currency(value) if value is not None else None


class ProviderRefundRequest(BaseSchema):
    """Provider-neutral request to create or initiate a refund."""

    refund_id: str = Field(min_length=1)
    payment_id: str = Field(min_length=1)
    provider_payment_id: str = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)
    metadata: dict[str, Any] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="metadata")


class ProviderPaymentCreateResult(BaseSchema):
    """Provider-neutral result returned after payment creation."""

    provider: str = Field(min_length=1, max_length=64)
    provider_payment_id: str = Field(min_length=1, max_length=255)
    provider_attempt_id: str | None = Field(default=None, min_length=1, max_length=255)
    status: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    redirect_url: str | None = Field(default=None, max_length=2000)
    client_payload: dict[str, Any] | None = None
    failure_code: str | None = Field(default=None, max_length=128)
    failure_message: str | None = Field(default=None, max_length=1000)
    safe_metadata: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in PAYMENT_STATUS_VALUES:
            raise ValueError("Unsupported provider-normalized payment status.")
        return value

    @field_validator("client_payload", "safe_metadata")
    @classmethod
    def validate_safe_payload(cls, value: dict[str, Any] | None, info) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name=str(info.field_name))


class ProviderPaymentStatusResult(ProviderPaymentCreateResult):
    """Provider-neutral result returned by a payment status lookup."""


class ProviderRefundResult(BaseSchema):
    """Provider-neutral result returned after refund creation or lookup."""

    provider: str = Field(min_length=1, max_length=64)
    provider_refund_id: str = Field(min_length=1, max_length=255)
    status: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    failure_code: str | None = Field(default=None, max_length=128)
    failure_message: str | None = Field(default=None, max_length=1000)
    safe_metadata: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in REFUND_STATUS_VALUES:
            raise ValueError("Unsupported provider-normalized refund status.")
        return value

    @field_validator("safe_metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="safe_metadata")


class ProviderWebhookEvent(BaseSchema):
    """Provider-neutral webhook event parsed by a provider adapter."""

    provider: str = Field(min_length=1, max_length=64)
    event_id: str | None = Field(default=None, min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=128)
    occurred_at: str | None = Field(default=None, max_length=64)
    payment: ProviderPaymentStatusResult | None = None
    refund: ProviderRefundResult | None = None
    safe_metadata: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("safe_metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="safe_metadata")


class PaymentProvider(ABC):
    """Abstract interface implemented by all payment provider adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the normalized provider identifier."""

    @abstractmethod
    async def create_payment(
        self,
        request: ProviderPaymentCreateRequest,
    ) -> ProviderPaymentCreateResult:
        """Create or initiate a payment with the provider."""

    @abstractmethod
    async def get_payment_status(
        self,
        request: ProviderPaymentStatusRequest,
    ) -> ProviderPaymentStatusResult:
        """Return the current provider-normalized payment status."""

    @abstractmethod
    async def cancel_payment(
        self,
        request: ProviderPaymentCancelRequest,
    ) -> ProviderPaymentStatusResult:
        """Cancel a provider payment when supported."""

    @abstractmethod
    async def refund_payment(
        self,
        request: ProviderRefundRequest,
    ) -> ProviderRefundResult:
        """Create or initiate a refund with the provider."""

    @abstractmethod
    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Verify that a raw webhook request was sent by the configured provider."""

    @abstractmethod
    async def parse_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str] | None = None,
    ) -> ProviderWebhookEvent:
        """Validate and normalize a provider webhook payload."""
