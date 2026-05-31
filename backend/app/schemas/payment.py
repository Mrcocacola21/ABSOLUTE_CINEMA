"""Payment, payment-attempt, and refund schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    PAYMENT_ATTEMPT_STATUS_VALUES,
    PAYMENT_STATUS_VALUES,
    PAYMENT_WEBHOOK_PROCESSING_STATUS_VALUES,
    REFUND_STATUS_VALUES,
    TICKET_STATUS_VALUES,
)
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText

DEFAULT_PAYMENT_CURRENCY: Final[str] = "UAH"
PAYMENT_SIMULATION_RESULT_VALUES: Final[tuple[str, ...]] = (
    "succeeded",
    "failed",
    "cancelled",
    "pending",
)
CUSTOMER_REFUND_SCOPE_VALUES: Final[tuple[str, ...]] = ("order", "tickets")
SAFE_MAPPING_MAX_DEPTH: Final[int] = 4
SAFE_MAPPING_MAX_KEYS: Final[int] = 50
SAFE_LIST_MAX_ITEMS: Final[int] = 100
SAFE_STRING_MAX_LENGTH: Final[int] = 2000
SAFE_SENSITIVE_KEY_MARKERS: Final[tuple[str, ...]] = (
    "authorization",
    "card",
    "client_secret",
    "cvv",
    "cvc",
    "password",
    "pan",
    "provider_secret",
    "secret",
    "signature",
    "token",
    "webhook_signature",
)


def normalize_currency(value: str) -> str:
    """Normalize and validate an ISO-like uppercase currency code."""
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a three-letter code.")
    return normalized


def normalize_provider(value: str) -> str:
    """Normalize a provider identifier used by the payment domain."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("provider must not be empty.")
    return normalized


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(marker in normalized for marker in SAFE_SENSITIVE_KEY_MARKERS)


def _validate_safe_value(value: object, *, path: str, depth: int) -> None:
    if depth > SAFE_MAPPING_MAX_DEPTH:
        raise ValueError(f"{path} exceeds the maximum nesting depth.")
    if isinstance(value, dict):
        if len(value) > SAFE_MAPPING_MAX_KEYS:
            raise ValueError(f"{path} contains too many keys.")
        for key, nested in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{path} contains an invalid key.")
            if _is_sensitive_key(key):
                raise ValueError(f"{path} contains sensitive key '{key}'.")
            _validate_safe_value(nested, path=f"{path}.{key}", depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > SAFE_LIST_MAX_ITEMS:
            raise ValueError(f"{path} contains too many list items.")
        for index, nested in enumerate(value):
            _validate_safe_value(nested, path=f"{path}[{index}]", depth=depth + 1)
        return
    if isinstance(value, str) and len(value) > SAFE_STRING_MAX_LENGTH:
        raise ValueError(f"{path} contains a string that is too long.")
    if value is None or isinstance(value, str | int | float | bool):
        return
    raise ValueError(f"{path} contains a value that is not JSON-safe.")


def validate_safe_snapshot(value: dict[str, Any] | None, *, field_name: str) -> dict[str, Any] | None:
    """Reject raw secrets, card data, and non-JSON values in snapshots."""
    if value is None:
        return None
    _validate_safe_value(value, path=field_name, depth=0)
    return value


class PaymentCreate(BaseSchema):
    """Internal payload used to create a payment aggregate."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    order_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    amount_minor: int = Field(gt=0)
    currency: str = Field(default=DEFAULT_PAYMENT_CURRENCY, min_length=3, max_length=3)
    provider: str = Field(min_length=1, max_length=64)
    provider_payment_id: str | None = Field(default=None, min_length=1, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=128)
    metadata: dict[str, Any] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="metadata")


class PaymentRead(PaymentCreate):
    """Payment aggregate returned by backend services."""

    id: str
    status: str
    failure_code: str | None = Field(default=None, max_length=128)
    failure_message: str | None = Field(default=None, max_length=1000)
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in PAYMENT_STATUS_VALUES:
            raise ValueError("Unsupported payment status.")
        return value

    @model_validator(mode="after")
    def validate_failure_state(self) -> "PaymentRead":
        if self.status == "failed" and not (self.failure_code or self.failure_message):
            raise ValueError("Failed payments should include a failure code or message.")
        return self


class PaymentInitiationRequest(BaseSchema):
    """Request payload for initiating provider-neutral payment checkout."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "return_url": "http://localhost:5173/profile/orders/6803a522e5d4c4d94e7e1a10",
                "cancel_url": "http://localhost:5173/profile/orders/6803a522e5d4c4d94e7e1a10",
                "metadata": {"source": "profile_order_details"},
            }
        },
    )

    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Optional client idempotency key. The `Idempotency-Key` header is preferred.",
    )
    return_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Frontend URL to return to after provider-side customer action.",
    )
    cancel_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Frontend URL to return to if provider-side customer action is cancelled.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Safe, non-sensitive metadata to pass through provider adapter boundaries.",
    )

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="metadata")


class PaymentInitiationRead(BaseSchema):
    """Provider-neutral response returned after payment initiation."""

    payment_id: str
    order_id: str
    provider: str
    status: str
    amount_minor: int = Field(gt=0)
    currency: str
    attempt_id: str | None = None
    attempt_status: str | None = None
    provider_payment_id: str | None = None
    provider_attempt_id: str | None = None
    redirect_url: str | None = None
    client_payload: dict[str, Any] | None = None
    expires_at: datetime | None = None
    reused: bool = False

    @field_validator("status")
    @classmethod
    def validate_payment_status(cls, value: str) -> str:
        if value not in PAYMENT_STATUS_VALUES:
            raise ValueError("Unsupported payment status.")
        return value

    @field_validator("attempt_status")
    @classmethod
    def validate_attempt_status(cls, value: str | None) -> str | None:
        if value is not None and value not in PAYMENT_ATTEMPT_STATUS_VALUES:
            raise ValueError("Unsupported payment attempt status.")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("client_payload")
    @classmethod
    def validate_client_payload(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="client_payload")


class PaymentSimulationRequest(BaseSchema):
    """Demo-only request for simulating the local fake-provider payment result."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "result": "succeeded",
            }
        },
    )

    result: str = Field(
        description=(
            "Fake-provider result to emit through the signed webhook pipeline. "
            "`pending` leaves the payment unresolved."
        ),
        json_schema_extra={"enum": list(PAYMENT_SIMULATION_RESULT_VALUES)},
    )

    @field_validator("result")
    @classmethod
    def validate_result(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PAYMENT_SIMULATION_RESULT_VALUES:
            raise ValueError("Unsupported payment simulation result.")
        return normalized


class PaymentAttemptCreate(BaseSchema):
    """Internal payload used to create a payment attempt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    payment_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    provider: str = Field(min_length=1, max_length=64)
    provider_attempt_id: str | None = Field(default=None, min_length=1, max_length=255)
    request_payload_snapshot: dict[str, Any] | None = None
    response_payload_snapshot: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("request_payload_snapshot", "response_payload_snapshot")
    @classmethod
    def validate_snapshot(cls, value: dict[str, Any] | None, info) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name=str(info.field_name))


class PaymentAttemptRead(PaymentAttemptCreate):
    """Payment attempt returned by backend services."""

    id: str
    status: str
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = Field(default=None, max_length=1000)
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in PAYMENT_ATTEMPT_STATUS_VALUES:
            raise ValueError("Unsupported payment attempt status.")
        return value


class PaymentDetailsRead(PaymentRead):
    """Payment aggregate with safe attempt history for API inspection."""

    attempts: list[PaymentAttemptRead] = Field(default_factory=list)


class PaymentWebhookEventCreate(BaseSchema):
    """Internal payload used to persist a received payment webhook event."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(min_length=1, max_length=64)
    provider_event_id: str | None = Field(default=None, min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=128)
    signature_verified: bool
    payload_hash: str = Field(min_length=16, max_length=128)
    payload_snapshot: dict[str, Any] | None = None
    processing_status: str
    processed_at: datetime | None = None
    error_message: str | None = Field(default=None, max_length=1000)
    payment_id: str | None = Field(default=None, min_length=1)
    order_id: str | None = Field(default=None, min_length=1)
    refund_id: str | None = Field(default=None, min_length=1)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("processing_status")
    @classmethod
    def validate_processing_status(cls, value: str) -> str:
        if value not in PAYMENT_WEBHOOK_PROCESSING_STATUS_VALUES:
            raise ValueError("Unsupported webhook processing status.")
        return value

    @field_validator("payload_snapshot")
    @classmethod
    def validate_payload_snapshot(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="payload_snapshot")


class PaymentWebhookEventRead(PaymentWebhookEventCreate):
    """Stored payment webhook event audit record."""

    id: str
    created_at: datetime
    updated_at: datetime | None = None


class PaymentWebhookProcessingRead(BaseSchema):
    """Provider-neutral webhook processing acknowledgment."""

    event_id: str | None = None
    provider: str
    provider_event_id: str | None = None
    event_type: str
    processing_status: str
    duplicate: bool = False
    payment_id: str | None = None
    refund_id: str | None = None
    order_id: str | None = None
    message: str

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("processing_status")
    @classmethod
    def validate_processing_status(cls, value: str) -> str:
        if value not in PAYMENT_WEBHOOK_PROCESSING_STATUS_VALUES:
            raise ValueError("Unsupported webhook processing status.")
        return value


class PaymentSimulationRead(BaseSchema):
    """Result returned after a demo fake-provider simulation is processed."""

    result: str
    payment: PaymentDetailsRead
    webhook: PaymentWebhookProcessingRead
    message: str

    @field_validator("result")
    @classmethod
    def validate_result(cls, value: str) -> str:
        if value not in PAYMENT_SIMULATION_RESULT_VALUES:
            raise ValueError("Unsupported payment simulation result.")
        return value


class PaymentAuditEventCreate(BaseSchema):
    """Internal safe audit event for sensitive payment lifecycle actions."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: str = Field(min_length=1, max_length=128)
    actor_type: str = Field(min_length=1, max_length=32)
    actor_id: str | None = Field(default=None, min_length=1, max_length=255)
    payment_id: str | None = Field(default=None, min_length=1)
    order_id: str | None = Field(default=None, min_length=1)
    refund_id: str | None = Field(default=None, min_length=1)
    webhook_event_id: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    old_status: str | None = Field(default=None, max_length=128)
    new_status: str | None = Field(default=None, max_length=128)
    reason: str | None = Field(default=None, max_length=500)
    safe_context: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        return normalize_provider(value) if value is not None else None

    @field_validator("safe_context")
    @classmethod
    def validate_safe_context(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="safe_context")


class PaymentAuditEventRead(PaymentAuditEventCreate):
    """Stored payment audit event."""

    id: str
    created_at: datetime


class RefundCreate(BaseSchema):
    """Internal payload used to create a refund record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    payment_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    amount_minor: int = Field(gt=0)
    currency: str = Field(default=DEFAULT_PAYMENT_CURRENCY, min_length=3, max_length=3)
    provider: str = Field(min_length=1, max_length=64)
    provider_refund_id: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=500)
    requested_by: str = Field(min_length=1, max_length=255)
    request_payload_snapshot: dict[str, Any] | None = None
    response_payload_snapshot: dict[str, Any] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return normalize_provider(value)

    @field_validator("request_payload_snapshot", "response_payload_snapshot")
    @classmethod
    def validate_snapshot(cls, value: dict[str, Any] | None, info) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name=str(info.field_name))


class RefundRead(RefundCreate):
    """Refund record returned by backend services."""

    id: str
    status: str
    failure_code: str | None = Field(default=None, max_length=128)
    failure_message: str | None = Field(default=None, max_length=1000)
    created_at: datetime
    updated_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in REFUND_STATUS_VALUES:
            raise ValueError("Unsupported refund status.")
        return value


class RefundRequest(BaseSchema):
    """Admin-facing request to create a full or partial financial refund."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "amount_minor": 2500,
                "reason": "customer_ticket_cancellation",
                "metadata": {"source": "admin_adjustment"},
            }
        },
    )

    amount_minor: int | None = Field(
        default=None,
        gt=0,
        description="Refund amount in minor currency units. Omit to refund the remaining refundable amount.",
    )
    reason: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Safe, non-sensitive metadata passed to the provider adapter.",
    )

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_safe_snapshot(value, field_name="metadata")


class CustomerRefundRequest(BaseSchema):
    """Customer-facing request to refund a cancelled ticket or a whole cancelled order."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "scope": "tickets",
                    "ticket_ids": ["6803a522e5d4c4d94e7e1a10"],
                    "reason": "customer_cancelled_ticket",
                },
                {
                    "scope": "order",
                    "ticket_ids": [],
                    "reason": "customer_cancelled_order",
                },
            ]
        },
    )

    scope: str = Field(
        default="order",
        description=(
            "`tickets` creates a partial refund for the selected cancelled ticket ids. "
            "`order` refunds the remaining refundable amount for a fully cancelled order."
        ),
    )
    ticket_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Cancelled ticket ids to refund when scope is `tickets`; leave empty for a full-order refund.",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional customer-safe reason stored on the refund record.",
    )

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        if value not in CUSTOMER_REFUND_SCOPE_VALUES:
            raise ValueError("Unsupported customer refund scope.")
        return value

    @field_validator("ticket_ids")
    @classmethod
    def validate_ticket_ids(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("Ticket ids must not be empty.")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Ticket ids must be unique.")
        return normalized

    @model_validator(mode="after")
    def validate_scope_payload(self) -> "CustomerRefundRequest":
        if self.scope == "tickets" and not self.ticket_ids:
            raise ValueError("At least one ticket id is required for a ticket refund.")
        if self.scope == "order" and self.ticket_ids:
            raise ValueError("Full-order refunds must not include ticket ids.")
        return self


class CustomerRefundRead(BaseSchema):
    """Result returned after a customer refund request is accepted by the refund subsystem."""

    refund: RefundRead
    payment: PaymentDetailsRead
    refunds: list[RefundRead] = Field(default_factory=list)
    refunds_count: int = Field(ge=0)
    refunded_amount_minor: int = Field(ge=0)
    remaining_refundable_amount_minor: int = Field(ge=0)
    latest_refund_status: str | None = None

    @field_validator("latest_refund_status")
    @classmethod
    def validate_latest_refund_status(cls, value: str | None) -> str | None:
        if value is not None and value not in REFUND_STATUS_VALUES:
            raise ValueError("Unsupported refund status.")
        return value


class AdminPaymentCustomerRead(BaseSchema):
    """Admin-safe customer reference shown beside a payment."""

    user_id: str
    name: str | None = None
    email: str | None = None


class AdminPaymentTicketImpactRead(BaseSchema):
    """Ticket-level payment/refund context for the admin payment details panel."""

    id: str
    seat_row: int = Field(ge=1)
    seat_number: int = Field(ge=1)
    seat_label: str
    price: float = Field(gt=0)
    status: str
    purchased_at: datetime | None = None
    cancelled_at: datetime | None = None
    checked_in_at: datetime | None = None
    refund_id: str | None = None
    refund_status: str | None = None
    refund_amount_minor: int = Field(default=0, ge=0)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in TICKET_STATUS_VALUES:
            raise ValueError("Unsupported ticket status.")
        return value

    @field_validator("refund_status")
    @classmethod
    def validate_refund_status(cls, value: str | None) -> str | None:
        if value is not None and value not in REFUND_STATUS_VALUES:
            raise ValueError("Unsupported refund status.")
        return value


class AdminPaymentOrderContextRead(BaseSchema):
    """Booking context shown in the admin payment workspace."""

    order_id: str
    order_status: str | None = None
    session_id: str | None = None
    movie_id: str | None = None
    movie_title: LocalizedText | None = None
    session_start_time: datetime | None = None
    session_end_time: datetime | None = None
    session_status: str | None = None
    total_price: float | None = None
    tickets_count: int = Field(default=0, ge=0)
    seats: list[str] = Field(default_factory=list)
    tickets: list[AdminPaymentTicketImpactRead] = Field(default_factory=list)
    expires_at: datetime | None = None


class AdminPaymentListItemRead(PaymentRead):
    """Payment row returned to the protected admin payment list."""

    attempts_count: int = Field(ge=0)
    refunds_count: int = Field(ge=0)
    refunded_amount_minor: int = Field(ge=0)
    remaining_refundable_amount_minor: int = Field(ge=0)
    refundable: bool
    latest_refund_status: str | None = None
    order_status: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None

    @field_validator("latest_refund_status")
    @classmethod
    def validate_latest_refund_status(cls, value: str | None) -> str | None:
        if value is not None and value not in REFUND_STATUS_VALUES:
            raise ValueError("Unsupported refund status.")
        return value


class AdminPaymentDetailsRead(PaymentRead):
    """Admin payment detail read model with related operational history."""

    attempts: list[PaymentAttemptRead] = Field(default_factory=list)
    refunds: list[RefundRead] = Field(default_factory=list)
    webhook_events: list[PaymentWebhookEventRead] = Field(default_factory=list)
    order: AdminPaymentOrderContextRead | None = None
    customer: AdminPaymentCustomerRead | None = None
    attempts_count: int = Field(ge=0)
    refunds_count: int = Field(ge=0)
    refunded_amount_minor: int = Field(ge=0)
    remaining_refundable_amount_minor: int = Field(ge=0)
    refundable: bool
    latest_refund_status: str | None = None

    @field_validator("latest_refund_status")
    @classmethod
    def validate_latest_refund_status(cls, value: str | None) -> str | None:
        if value is not None and value not in REFUND_STATUS_VALUES:
            raise ValueError("Unsupported refund status.")
        return value


class PaymentReportPeriodRead(BaseSchema):
    """Date window and timestamp semantics used by payment revenue reporting."""

    date_from: datetime | None = Field(
        default=None,
        description="Inclusive lower bound for payment/refund timestamps. Null means all earlier history is included.",
    )
    date_to: datetime | None = Field(
        default=None,
        description="Inclusive upper bound for payment/refund timestamps. Null means all later history is included.",
    )
    payment_timestamp_basis: str = Field(
        default="payment.created_at",
        description="Timestamp used to include payments in status counts and gross revenue.",
    )
    refund_timestamp_basis: str = Field(
        default="refund.created_at",
        description="Timestamp used to include succeeded refunds in refunded amount and net revenue.",
    )


class PaymentReportSummaryRead(BaseSchema):
    """Financially coherent payment summary for an administrator-selected period."""

    currency: str
    total_payments_count: int = Field(ge=0)
    succeeded_payments_count: int = Field(
        ge=0,
        description="Payments with captured financial value: succeeded, partially_refunded, or refunded.",
    )
    failed_payments_count: int = Field(ge=0)
    pending_payments_count: int = Field(
        ge=0,
        description="Payments still in created, pending, or requires_action states.",
    )
    cancelled_payments_count: int = Field(ge=0)
    expired_payments_count: int = Field(ge=0)
    refunded_payments_count: int = Field(ge=0)
    partially_refunded_payments_count: int = Field(ge=0)
    gross_revenue_minor: int = Field(
        ge=0,
        description="Sum of financially succeeded payment amounts in the selected payment period.",
    )
    refunded_amount_minor: int = Field(
        ge=0,
        description="Sum of succeeded refund amounts in the selected refund period.",
    )
    net_revenue_minor: int = Field(description="Gross revenue minus succeeded refunds for the selected period.")
    succeeded_orders_count: int = Field(ge=0)
    paid_tickets_count: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=1)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)


class PaymentReportSessionAggregateRead(BaseSchema):
    """Revenue aggregate linked to one cinema session."""

    session_id: str
    movie_id: str | None = None
    movie_title: LocalizedText | None = None
    session_start_time: datetime | None = None
    session_end_time: datetime | None = None
    session_status: str | None = None
    currency: str
    succeeded_payments_count: int = Field(ge=0)
    succeeded_orders_count: int = Field(ge=0)
    paid_tickets_count: int = Field(ge=0)
    gross_revenue_minor: int = Field(ge=0)
    refunded_amount_minor: int = Field(ge=0)
    net_revenue_minor: int

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)


class PaymentReportMovieAggregateRead(BaseSchema):
    """Revenue aggregate linked to one movie title."""

    movie_id: str
    movie_title: LocalizedText | None = None
    currency: str
    paid_sessions_count: int = Field(ge=0)
    succeeded_payments_count: int = Field(ge=0)
    succeeded_orders_count: int = Field(ge=0)
    paid_tickets_count: int = Field(ge=0)
    gross_revenue_minor: int = Field(ge=0)
    refunded_amount_minor: int = Field(ge=0)
    net_revenue_minor: int

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return normalize_currency(value)


class PaymentReportRead(BaseSchema):
    """Admin payment revenue report with global, session, and movie aggregates."""

    generated_at: datetime
    period: PaymentReportPeriodRead
    summary: PaymentReportSummaryRead
    sessions: list[PaymentReportSessionAggregateRead] = Field(default_factory=list)
    movies: list[PaymentReportMovieAggregateRead] = Field(default_factory=list)
