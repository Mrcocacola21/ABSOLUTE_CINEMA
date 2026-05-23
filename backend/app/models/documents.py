"""Typed document models representing raw MongoDB payloads."""

from __future__ import annotations

from datetime import datetime
from typing import NotRequired, TypedDict


class UserDocument(TypedDict):
    """Raw MongoDB user document."""

    name: str
    email: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class MovieDocument(TypedDict):
    """Raw MongoDB movie document."""

    title: dict[str, str] | str
    description: dict[str, str] | str
    duration_minutes: int
    poster_url: NotRequired[str | None]
    poster_file_url: NotRequired[str | None]
    age_rating: NotRequired[str | None]
    genres: list[str]
    status: str
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class SessionDocument(TypedDict):
    """Raw MongoDB session document."""

    movie_id: str
    start_time: datetime
    end_time: datetime
    price: float
    status: str
    total_seats: int
    available_seats: int
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class OrderDocument(TypedDict):
    """Raw MongoDB order document."""

    user_id: str
    session_id: str
    status: str
    total_price: float
    tickets_count: int
    expires_at: NotRequired[datetime | None]
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class TicketDocument(TypedDict):
    """Raw MongoDB ticket document."""

    order_id: str
    user_id: str
    session_id: str
    seat_row: int
    seat_number: int
    price: float
    status: str
    reserved_at: NotRequired[datetime | None]
    expires_at: NotRequired[datetime | None]
    purchased_at: NotRequired[datetime | None]
    updated_at: NotRequired[datetime | None]
    cancelled_at: NotRequired[datetime | None]
    checked_in_at: NotRequired[datetime | None]


class PaymentDocument(TypedDict):
    """Raw MongoDB payment aggregate document."""

    order_id: str
    user_id: str
    amount_minor: int
    currency: str
    status: str
    provider: str
    provider_payment_id: NotRequired[str | None]
    idempotency_key: str
    failure_code: NotRequired[str | None]
    failure_message: NotRequired[str | None]
    metadata: NotRequired[dict[str, object] | None]
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class PaymentAttemptDocument(TypedDict):
    """Raw MongoDB payment attempt document."""

    payment_id: str
    order_id: str
    provider: str
    status: str
    provider_attempt_id: NotRequired[str | None]
    request_payload_snapshot: NotRequired[dict[str, object] | None]
    response_payload_snapshot: NotRequired[dict[str, object] | None]
    error_code: NotRequired[str | None]
    error_message: NotRequired[str | None]
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class PaymentWebhookEventDocument(TypedDict):
    """Raw MongoDB payment webhook event document."""

    provider: str
    provider_event_id: NotRequired[str | None]
    event_type: str
    signature_verified: bool
    payload_hash: str
    payload_snapshot: NotRequired[dict[str, object] | None]
    processing_status: str
    processed_at: NotRequired[datetime | None]
    error_message: NotRequired[str | None]
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class RefundDocument(TypedDict):
    """Raw MongoDB refund document."""

    payment_id: str
    order_id: str
    amount_minor: int
    currency: str
    status: str
    provider: str
    provider_refund_id: NotRequired[str | None]
    reason: str
    failure_code: NotRequired[str | None]
    failure_message: NotRequired[str | None]
    created_at: datetime
    updated_at: NotRequired[datetime | None]
