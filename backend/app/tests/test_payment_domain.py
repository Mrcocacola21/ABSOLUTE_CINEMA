"""Unit tests for the provider-neutral payment domain skeleton."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import inspect
import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.constants import (
    OrderStatuses,
    PaymentAttemptStatuses,
    PaymentStatuses,
    PaymentWebhookProcessingStatuses,
    RefundStatuses,
    TicketStatuses,
)
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import RedactingFormatter, configure_logging, sanitize_for_logging
from app.payments.providers.base import (
    PaymentProviderError,
    ProviderPaymentCreateRequest,
    ProviderPaymentCreateResult,
    ProviderRefundRequest,
    ProviderRefundResult,
)
from app.payments.providers.fake import FakePaymentProvider
from app.schemas.payment import CustomerRefundRequest, PaymentCreate, PaymentRead, RefundCreate
from app.schemas.user import UserRead
from app.services.payment import PaymentService
from app.services.refund import RefundService


class FakeOrderRepository:
    """Small order repository double for payment-service tests."""

    def __init__(self, orders: list[dict[str, object]]) -> None:
        self.orders = {str(order["id"]): dict(order) for order in orders}

    async def get_by_id(self, order_id: str, **_: object) -> dict[str, object] | None:
        order = self.orders.get(order_id)
        return dict(order) if order is not None else None

    async def list_by_ids(self, order_ids: list[str], **_: object) -> list[dict[str, object]]:
        return [dict(self.orders[order_id]) for order_id in order_ids if order_id in self.orders]

    async def update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        **_: object,
    ) -> dict[str, object] | None:
        order = self.orders.get(order_id)
        if order is None:
            return None
        self.orders[order_id] = {**order, **updates, "updated_at": updated_at}
        return dict(self.orders[order_id])


class FakePaymentRepository:
    """In-memory payment repository double."""

    def __init__(self, payments: list[dict[str, object]] | None = None) -> None:
        self.payments = {str(payment["id"]): dict(payment) for payment in payments or []}
        self.created_count = 0

    async def create_payment(self, document: dict[str, object], **_: object) -> dict[str, object]:
        self.created_count += 1
        payment_id = f"payment-{self.created_count}"
        payment = {**document, "id": payment_id}
        self.payments[payment_id] = dict(payment)
        return dict(payment)

    async def get_by_id(self, payment_id: str, **_: object) -> dict[str, object] | None:
        payment = self.payments.get(payment_id)
        return dict(payment) if payment is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str, **_: object) -> dict[str, object] | None:
        for payment in self.payments.values():
            if payment["idempotency_key"] == idempotency_key:
                return dict(payment)
        return None

    async def list_by_order(self, order_id: str, **_: object) -> list[dict[str, object]]:
        return [
            dict(payment)
            for payment in reversed(list(self.payments.values()))
            if payment["order_id"] == order_id
        ]

    async def list_admin_payments(
        self,
        *,
        status: str | None = None,
        provider: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        **_: object,
    ) -> list[dict[str, object]]:
        _ = search
        payments = [
            dict(payment)
            for payment in reversed(list(self.payments.values()))
            if (status is None or payment["status"] == status)
            and (provider is None or payment["provider"] == provider)
        ]
        return payments[offset : offset + limit]

    async def list_admin_payments_for_report(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 5000,
        **_: object,
    ) -> list[dict[str, object]]:
        payments = []
        for payment in reversed(list(self.payments.values())):
            created_at = payment["created_at"]
            if date_from is not None and created_at < date_from:
                continue
            if date_to is not None and created_at > date_to:
                continue
            payments.append(dict(payment))
        return payments[:limit]

    async def get_by_provider_payment_id(
        self,
        *,
        provider: str,
        provider_payment_id: str,
        **_: object,
    ) -> dict[str, object] | None:
        for payment in self.payments.values():
            if payment["provider"] == provider and payment.get("provider_payment_id") == provider_payment_id:
                return dict(payment)
        return None

    async def update_status(
        self,
        payment_id: str,
        *,
        status: str,
        updated_at: datetime,
        provider_payment_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        current_statuses: set[str] | None = None,
        **_: object,
    ) -> dict[str, object] | None:
        payment = self.payments.get(payment_id)
        if payment is None:
            return None
        if current_statuses is not None and payment["status"] not in current_statuses:
            return None
        payment["status"] = status
        payment["updated_at"] = updated_at
        payment["failure_code"] = failure_code
        payment["failure_message"] = failure_message
        if provider_payment_id is not None:
            payment["provider_payment_id"] = provider_payment_id
        return dict(payment)


class ConcurrentCreateConflictPaymentRepository(FakePaymentRepository):
    """Repository double that simulates a concurrent active payment insert."""

    async def create_payment(self, document: dict[str, object], **_: object) -> dict[str, object]:
        self.created_count += 1
        payment = {
            **document,
            "id": "payment-race",
            "status": PaymentStatuses.PENDING,
            "provider_payment_id": "fake-pay-payment-race",
            "updated_at": datetime.now(tz=timezone.utc),
        }
        self.payments["payment-race"] = dict(payment)
        raise ConflictException("Duplicate payment idempotency key.")


class FakePaymentAttemptRepository:
    """In-memory payment attempt repository double."""

    def __init__(self) -> None:
        self.attempts: dict[str, dict[str, object]] = {}
        self.created_count = 0

    async def create_attempt(self, document: dict[str, object], **_: object) -> dict[str, object]:
        self.created_count += 1
        attempt_id = f"attempt-{self.created_count}"
        attempt = {**document, "id": attempt_id}
        self.attempts[attempt_id] = dict(attempt)
        return dict(attempt)

    async def get_by_id(self, attempt_id: str, **_: object) -> dict[str, object] | None:
        attempt = self.attempts.get(attempt_id)
        return dict(attempt) if attempt is not None else None

    async def list_by_payment(self, payment_id: str, **_: object) -> list[dict[str, object]]:
        return [
            dict(attempt)
            for attempt in reversed(list(self.attempts.values()))
            if attempt["payment_id"] == payment_id
        ]

    async def update_status(
        self,
        attempt_id: str,
        *,
        status: str,
        updated_at: datetime,
        provider_attempt_id: str | None = None,
        response_payload_snapshot: dict[str, object] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        **_: object,
    ) -> dict[str, object] | None:
        attempt = self.attempts.get(attempt_id)
        if attempt is None:
            return None
        attempt["status"] = status
        attempt["updated_at"] = updated_at
        attempt["error_code"] = error_code
        attempt["error_message"] = error_message
        if provider_attempt_id is not None:
            attempt["provider_attempt_id"] = provider_attempt_id
        if response_payload_snapshot is not None:
            attempt["response_payload_snapshot"] = response_payload_snapshot
        return dict(attempt)


class FakePaymentWebhookEventRepository:
    """In-memory payment webhook event repository double."""

    def __init__(self) -> None:
        self.events: dict[str, dict[str, object]] = {}
        self.created_count = 0

    async def create_event(self, document: dict[str, object], **_: object) -> dict[str, object]:
        self.created_count += 1
        event_id = f"webhook-{self.created_count}"
        event = {**document, "id": event_id}
        self.events[event_id] = dict(event)
        return dict(event)

    async def get_by_provider_event_id(
        self,
        *,
        provider: str,
        provider_event_id: str,
        **_: object,
    ) -> dict[str, object] | None:
        for event in self.events.values():
            if event["provider"] == provider and event.get("provider_event_id") == provider_event_id:
                return dict(event)
        return None

    async def update_processing_status(
        self,
        event_id: str,
        *,
        processing_status: str,
        updated_at: datetime,
        processed_at: datetime | None = None,
        error_message: str | None = None,
        payment_id: str | None = None,
        order_id: str | None = None,
        refund_id: str | None = None,
        **_: object,
    ) -> dict[str, object] | None:
        event = self.events.get(event_id)
        if event is None:
            return None
        event["processing_status"] = processing_status
        event["updated_at"] = updated_at
        event["error_message"] = error_message
        if processed_at is not None:
            event["processed_at"] = processed_at
        if payment_id is not None:
            event["payment_id"] = payment_id
        if order_id is not None:
            event["order_id"] = order_id
        if refund_id is not None:
            event["refund_id"] = refund_id
        return dict(event)

    async def list_by_payment_context(
        self,
        *,
        payment_id: str,
        order_id: str,
        provider: str,
        provider_payment_id: str | None = None,
        provider_refund_ids: list[str] | None = None,
        **_: object,
    ) -> list[dict[str, object]]:
        refund_ids = set(provider_refund_ids or [])
        matched: list[dict[str, object]] = []
        for event in reversed(list(self.events.values())):
            if event.get("payment_id") == payment_id or event.get("order_id") == order_id:
                matched.append(dict(event))
                continue
            if event.get("provider") != provider:
                continue
            snapshot = event.get("payload_snapshot")
            if not isinstance(snapshot, dict):
                continue
            payment_snapshot = snapshot.get("payment")
            if isinstance(payment_snapshot, dict) and provider_payment_id in {
                payment_snapshot.get("provider_payment_id"),
                payment_snapshot.get("id"),
            }:
                matched.append(dict(event))
                continue
            refund_snapshot = snapshot.get("refund")
            if isinstance(refund_snapshot, dict) and refund_ids.intersection(
                {
                    str(refund_snapshot.get("provider_refund_id")),
                    str(refund_snapshot.get("id")),
                }
            ):
                matched.append(dict(event))
        return matched


class FakePaymentAuditEventRepository:
    """In-memory payment audit event repository double."""

    def __init__(self) -> None:
        self.events: dict[str, dict[str, object]] = {}
        self.created_count = 0

    async def create_event(self, document: dict[str, object], **_: object) -> dict[str, object]:
        self.created_count += 1
        event_id = f"audit-{self.created_count}"
        event = {**document, "id": event_id}
        self.events[event_id] = dict(event)
        return dict(event)


class FakeRefundRepository:
    """In-memory refund repository double."""

    def __init__(self, refunds: list[dict[str, object]] | None = None) -> None:
        self.refunds: dict[str, dict[str, object]] = {
            str(refund["id"]): dict(refund)
            for refund in refunds or []
        }
        self.created_count = 0

    async def create_refund(self, document: dict[str, object], **_: object) -> dict[str, object]:
        self.created_count += 1
        refund_id = f"refund-{self.created_count}"
        refund = {**document, "id": refund_id}
        self.refunds[refund_id] = dict(refund)
        return dict(refund)

    async def get_by_id(self, refund_id: str, **_: object) -> dict[str, object] | None:
        refund = self.refunds.get(refund_id)
        return dict(refund) if refund is not None else None

    async def list_by_payment(self, payment_id: str, **_: object) -> list[dict[str, object]]:
        return [dict(refund) for refund in self.refunds.values() if refund["payment_id"] == payment_id]

    async def list_by_order(self, order_id: str, **_: object) -> list[dict[str, object]]:
        return [dict(refund) for refund in self.refunds.values() if refund["order_id"] == order_id]

    async def list_admin_refunds_for_report(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 5000,
        **_: object,
    ) -> list[dict[str, object]]:
        refunds = []
        for refund in reversed(list(self.refunds.values())):
            created_at = refund["created_at"]
            if date_from is not None and created_at < date_from:
                continue
            if date_to is not None and created_at > date_to:
                continue
            refunds.append(dict(refund))
        return refunds[:limit]

    async def get_by_provider_refund_id(
        self,
        *,
        provider: str,
        provider_refund_id: str,
        **_: object,
    ) -> dict[str, object] | None:
        for refund in self.refunds.values():
            if refund["provider"] == provider and refund.get("provider_refund_id") == provider_refund_id:
                return dict(refund)
        return None

    async def update_refund(
        self,
        refund_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        **_: object,
    ) -> dict[str, object] | None:
        refund = self.refunds.get(refund_id)
        if refund is None:
            return None
        refund.update(updates)
        refund["updated_at"] = updated_at
        return dict(refund)

    async def update_status(
        self,
        refund_id: str,
        *,
        status: str,
        updated_at: datetime,
        provider_refund_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        response_payload_snapshot: dict[str, object] | None = None,
        **_: object,
    ) -> dict[str, object] | None:
        refund = self.refunds.get(refund_id)
        if refund is None:
            return None
        refund["status"] = status
        refund["updated_at"] = updated_at
        refund["failure_code"] = failure_code
        refund["failure_message"] = failure_message
        if provider_refund_id is not None:
            refund["provider_refund_id"] = provider_refund_id
        if response_payload_snapshot is not None:
            refund["response_payload_snapshot"] = response_payload_snapshot
        return dict(refund)


class FakeTicketRepository:
    """In-memory ticket repository double for webhook tests."""

    def __init__(self, tickets: list[dict[str, object]] | None = None) -> None:
        self.tickets = [dict(ticket) for ticket in tickets or []]

    async def list_by_order(self, order_id: str, **_: object) -> list[dict[str, object]]:
        return [dict(ticket) for ticket in self.tickets if ticket["order_id"] == order_id]

    async def mark_reserved_by_order_purchased(
        self,
        order_id: str,
        *,
        purchased_at: datetime,
        updated_at: datetime,
        **_: object,
    ) -> int:
        updated = 0
        for index, ticket in enumerate(self.tickets):
            if ticket["order_id"] == order_id and ticket["status"] == "reserved" and ticket["expires_at"] > purchased_at:
                self.tickets[index] = {
                    **ticket,
                    "status": "purchased",
                    "purchased_at": purchased_at,
                    "updated_at": updated_at,
                    "cancelled_at": None,
                }
                updated += 1
        return updated

    async def update_many_status_by_order(
        self,
        order_id: str,
        *,
        status: str,
        updated_at: datetime,
        cancelled_at: datetime | None = None,
        current_status: str | None = None,
        **_: object,
    ) -> int:
        updated = 0
        for index, ticket in enumerate(self.tickets):
            if ticket["order_id"] != order_id:
                continue
            if current_status is not None and ticket["status"] != current_status:
                continue
            self.tickets[index] = {
                **ticket,
                "status": status,
                "updated_at": updated_at,
                "cancelled_at": cancelled_at,
            }
            updated += 1
        return updated


class FakeSessionRepository:
    """In-memory session repository double for webhook tests."""

    def __init__(self, sessions: list[dict[str, object]] | None = None) -> None:
        now = datetime.now(tz=timezone.utc)
        default_session = {
            "id": "session-1",
            "movie_id": "movie-1",
            "start_time": now + timedelta(days=1),
            "end_time": now + timedelta(days=1, hours=2),
            "price": 123.45,
            "status": "scheduled",
            "total_seats": 96,
            "available_seats": 95,
            "created_at": now,
            "updated_at": None,
        }
        self.sessions = {
            str(session["id"]): dict(session)
            for session in sessions or [default_session]
        }
        self.session = self.sessions.get("session-1") or next(iter(self.sessions.values()))
        self.restored_quantity = 0

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime, **_: object) -> int:
        _ = (current_time, updated_at)
        return 0

    async def get_by_id(self, session_id: str, **_: object) -> dict[str, object] | None:
        session = self.sessions.get(session_id)
        return dict(session) if session is not None else None

    async def list_by_ids(self, session_ids: list[str], **_: object) -> list[dict[str, object]]:
        return [dict(self.sessions[session_id]) for session_id in session_ids if session_id in self.sessions]

    async def increment_available_seats(
        self,
        session_id: str,
        *,
        updated_at: datetime,
        quantity: int = 1,
        **_: object,
    ) -> bool:
        _ = updated_at
        session = self.sessions.get(session_id)
        if session is None:
            return False
        session["available_seats"] = int(session["available_seats"]) + quantity
        if session_id == self.session["id"]:
            self.session = session
        self.restored_quantity += quantity
        return True


class FakeMovieRepository:
    """In-memory movie repository double for payment report tests."""

    def __init__(self, movies: list[dict[str, object]]) -> None:
        self.movies = {str(movie["id"]): dict(movie) for movie in movies}

    async def get_by_id(self, movie_id: str, **_: object) -> dict[str, object] | None:
        movie = self.movies.get(movie_id)
        return dict(movie) if movie is not None else None

    async def list_by_ids(self, movie_ids: list[str], **_: object) -> list[dict[str, object]]:
        return [dict(self.movies[movie_id]) for movie_id in movie_ids if movie_id in self.movies]


class FailingCreatePaymentProvider(FakePaymentProvider):
    """Provider double that fails payment creation after the local attempt starts."""

    async def create_payment(self, request: ProviderPaymentCreateRequest) -> ProviderPaymentCreateResult:
        raise PaymentProviderError(
            "Provider is unavailable.",
            code="provider_unavailable",
            safe_metadata={"operation": "create_payment", "payment_id": request.payment_id},
        )


class RecordingFakePaymentProvider(FakePaymentProvider):
    """Fake provider that records the normalized provider request."""

    def __init__(self) -> None:
        super().__init__()
        self.create_requests: list[ProviderPaymentCreateRequest] = []
        self.refund_requests: list[ProviderRefundRequest] = []

    async def create_payment(self, request: ProviderPaymentCreateRequest) -> ProviderPaymentCreateResult:
        self.create_requests.append(request)
        return await super().create_payment(request)

    async def refund_payment(self, request: ProviderRefundRequest) -> ProviderRefundResult:
        self.refund_requests.append(request)
        return await super().refund_payment(request)


class FailingRefundPaymentProvider(FakePaymentProvider):
    """Provider double that fails refund creation after the local refund is recorded."""

    async def refund_payment(self, request: ProviderRefundRequest) -> ProviderRefundResult:
        raise PaymentProviderError(
            "Refund endpoint is unavailable.",
            code="refund_provider_unavailable",
            safe_metadata={"operation": "refund_payment", "refund_id": request.refund_id},
        )


async def run_without_real_transaction(callback, *, operation_name: str, **_: object) -> object:
    """Execute a transactional service callback without opening a MongoDB session."""
    _ = operation_name
    return await callback(object())


def sign_fake_webhook_payload(
    payload: dict[str, object],
    *,
    secret: str = "fake-webhook-secret",
) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return raw_body, signature


def build_order(
    order_id: str = "order-1",
    *,
    total_price: float = 123.45,
    status: str = OrderStatuses.PENDING_PAYMENT,
    expires_at: datetime | None = None,
    user_id: str = "user-1",
    session_id: str = "session-1",
    tickets_count: int = 1,
) -> dict[str, object]:
    return {
        "id": order_id,
        "user_id": user_id,
        "session_id": session_id,
        "status": status,
        "total_price": total_price,
        "tickets_count": tickets_count,
        "expires_at": expires_at or datetime.now(tz=timezone.utc) + timedelta(minutes=15),
        "created_at": datetime.now(tz=timezone.utc),
        "updated_at": None,
    }


def build_payment(
    payment_id: str = "payment-1",
    *,
    order_id: str = "order-1",
    user_id: str = "user-1",
    amount_minor: int = 10000,
    status: str = "succeeded",
    provider: str = "demo",
    provider_payment_id: str | None = None,
    currency: str = "UAH",
    created_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": payment_id,
        "order_id": order_id,
        "user_id": user_id,
        "amount_minor": amount_minor,
        "currency": currency,
        "status": status,
        "provider": provider,
        "provider_payment_id": provider_payment_id,
        "idempotency_key": f"idempotency-{payment_id}",
        "failure_code": None,
        "failure_message": None,
        "metadata": None,
        "created_at": created_at or datetime.now(tz=timezone.utc),
        "updated_at": None,
    }


def build_refund(
    refund_id: str = "refund-1",
    *,
    payment_id: str = "payment-1",
    order_id: str = "order-1",
    amount_minor: int = 1000,
    status: str = RefundStatuses.SUCCEEDED,
    currency: str = "UAH",
    created_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "id": refund_id,
        "payment_id": payment_id,
        "order_id": order_id,
        "user_id": "user-1",
        "amount_minor": amount_minor,
        "currency": currency,
        "status": status,
        "provider": "fake",
        "provider_refund_id": f"fake-refund-{refund_id}",
        "reason": "admin_adjustment",
        "requested_by": "admin:user-1",
        "request_payload_snapshot": None,
        "response_payload_snapshot": None,
        "failure_code": None,
        "failure_message": None,
        "created_at": created_at or datetime.now(tz=timezone.utc),
        "updated_at": None,
    }


def build_reserved_ticket(
    ticket_id: str = "ticket-1",
    *,
    order_id: str = "order-1",
    user_id: str = "user-1",
    seat_number: int = 1,
    price: float = 123.45,
    status: str = TicketStatuses.RESERVED,
    cancelled_at: datetime | None = None,
    checked_in_at: datetime | None = None,
) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": ticket_id,
        "user_id": user_id,
        "order_id": order_id,
        "session_id": "session-1",
        "seat_row": 1,
        "seat_number": seat_number,
        "price": price,
        "status": status,
        "reserved_at": now,
        "expires_at": now + timedelta(minutes=15),
        "purchased_at": now if status in {TicketStatuses.PURCHASED, TicketStatuses.CANCELLED} else None,
        "cancelled_at": cancelled_at if cancelled_at is not None else (now if status == TicketStatuses.CANCELLED else None),
        "checked_in_at": checked_in_at,
        "created_at": now,
        "updated_at": None,
    }


def build_user(*, user_id: str = "user-1", role: str = "user") -> UserRead:
    return UserRead(
        id=user_id,
        name="Payment User",
        email=f"{user_id}@example.com",
        role=role,
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
        updated_at=None,
    )


def test_payment_log_sanitizer_redacts_webhook_and_payment_secrets() -> None:
    payload = {
        "Authorization": "Bearer access-token-secret",
        "x-fake-payment-signature": "signed-webhook-secret",
        "nested": {
            "client_secret": "provider-client-secret",
            "card_number": "4111111111111111",
            "safe_id": "payment-1",
        },
    }

    sanitized = sanitize_for_logging(payload)

    assert sanitized["Authorization"] == "<redacted>"
    assert sanitized["x-fake-payment-signature"] == "<redacted>"
    assert sanitized["nested"]["client_secret"] == "<redacted>"
    assert sanitized["nested"]["card_number"] == "<redacted>"
    assert sanitized["nested"]["safe_id"] == "payment-1"


def test_redacting_formatter_masks_sensitive_payment_log_strings() -> None:
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="headers={'x-fake-payment-signature': 'signed-webhook-secret', 'Authorization': 'Bearer access-token-secret'}",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)

    assert "signed-webhook-secret" not in rendered
    assert "access-token-secret" not in rendered
    assert "<redacted>" in rendered


@pytest.mark.asyncio
async def test_payment_webhook_logging_does_not_leak_real_flow_secrets(tmp_path: Path) -> None:
    app_log = tmp_path / "app.log"
    payments_log = tmp_path / "payments.log"
    audit_log = tmp_path / "audit.log"
    configure_logging(
        "INFO",
        app_log_file=str(app_log),
        payments_log_file=str(payments_log),
        audit_log_file=str(audit_log),
    )

    audit_events = FakePaymentAuditEventRepository()
    webhook_events = FakePaymentWebhookEventRepository()
    service, _, _ = build_payment_service(
        payment_webhook_event_repository=webhook_events,
        payment_audit_event_repository=audit_events,
    )
    raw_body, _ = sign_fake_webhook_payload(
        {
            "event_id": "evt-secret-leak-probe",
            "event_type": "payment.updated",
            "authorization": "Bearer body-authorization-secret",
            "provider_secret": "body-provider-secret",
            "webhook_signature": "body-webhook-signature-secret",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "paid",
                "amount_minor": 12345,
                "currency": "UAH",
                "client_secret": "body-client-secret",
            },
        }
    )

    with pytest.raises(AuthenticationException):
        await service.process_provider_webhook(
            raw_body=raw_body,
            headers={
                "authorization": "Bearer header-authorization-secret",
                "x-fake-payment-signature": "header-webhook-signature-secret",
                "provider-secret": "header-provider-secret",
            },
        )
    _flush_configured_logging_handlers()

    app_output = app_log.read_text(encoding="utf-8")
    payments_output = payments_log.read_text(encoding="utf-8")
    audit_output = audit_log.read_text(encoding="utf-8")
    combined_output = "\n".join([app_output, payments_output, audit_output])

    assert "Rejected payment webhook with invalid signature" in payments_output
    assert "webhook.rejected_invalid_signature" in audit_output
    assert audit_events.created_count == 1
    assert webhook_events.created_count == 1

    for raw_secret in (
        "body-authorization-secret",
        "body-provider-secret",
        "body-webhook-signature-secret",
        "body-client-secret",
        "header-authorization-secret",
        "header-webhook-signature-secret",
        "header-provider-secret",
    ):
        assert raw_secret not in combined_output
        assert raw_secret not in str(webhook_events.events)
        assert raw_secret not in str(audit_events.events)


def _flush_configured_logging_handlers() -> None:
    for logger_name in ("", "cinema_showcase", "cinema_showcase.payments", "cinema_showcase.audit"):
        for handler in logging.getLogger(logger_name).handlers:
            handler.flush()


def build_payment_service(
    *,
    order: dict[str, object] | None = None,
    payment_repository: FakePaymentRepository | None = None,
    payment_webhook_event_repository: FakePaymentWebhookEventRepository | None = None,
    payment_audit_event_repository: FakePaymentAuditEventRepository | None = None,
    refund_repository: FakeRefundRepository | None = None,
    ticket_repository: FakeTicketRepository | None = None,
    session_repository: FakeSessionRepository | None = None,
    payment_provider: FakePaymentProvider | None = None,
) -> tuple[PaymentService, FakePaymentRepository, FakePaymentAttemptRepository]:
    payments = payment_repository or FakePaymentRepository()
    attempts = FakePaymentAttemptRepository()
    service = PaymentService(
        payment_repository=payments,
        payment_attempt_repository=attempts,
        payment_webhook_event_repository=payment_webhook_event_repository or FakePaymentWebhookEventRepository(),
        payment_audit_event_repository=payment_audit_event_repository,
        refund_repository=refund_repository or FakeRefundRepository(),
        order_repository=FakeOrderRepository([order or build_order()]),
        ticket_repository=ticket_repository or FakeTicketRepository(),
        session_repository=session_repository or FakeSessionRepository(),
        payment_provider=payment_provider or FakePaymentProvider(),
    )
    return service, payments, attempts


@pytest.mark.asyncio
async def test_payment_service_creates_payment_for_order_through_provider_with_idempotency() -> None:
    service, payment_repository, attempts = build_payment_service()

    payment = await service.create_payment_for_order(
        order_id="order-1",
        idempotency_key="idem-order-1",
        metadata={"flow": "domain-test"},
    )

    assert payment.order_id == "order-1"
    assert payment.user_id == "user-1"
    assert payment.amount_minor == 12345
    assert payment.currency == "UAH"
    assert payment.provider == "fake"
    assert payment.provider_payment_id == "fake-pay-payment-1"
    assert payment.status == PaymentStatuses.PENDING
    assert payment_repository.created_count == 1
    assert attempts.attempts["attempt-1"]["status"] == PaymentAttemptStatuses.SUCCEEDED
    assert attempts.attempts["attempt-1"]["provider_attempt_id"] == "fake-attempt-payment-1"
    assert attempts.attempts["attempt-1"]["response_payload_snapshot"]["status"] == PaymentStatuses.PENDING

    repeated = await service.create_payment_for_order(
        order_id="order-1",
        idempotency_key="idem-order-1",
    )
    assert repeated.id == payment.id
    assert payment_repository.created_count == 1


@pytest.mark.asyncio
async def test_payment_initiation_returns_provider_neutral_payload_and_reuses_active_payment() -> None:
    provider = RecordingFakePaymentProvider()
    service, payment_repository, attempts = build_payment_service(payment_provider=provider)

    initiation = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="idem-order-1",
        metadata={"source": "profile"},
        return_url="http://localhost:5173/profile/orders/order-1",
    )

    assert initiation.payment_id == "payment-1"
    assert initiation.order_id == "order-1"
    assert initiation.status == PaymentStatuses.PENDING
    assert initiation.provider == "fake"
    assert initiation.attempt_id == "attempt-1"
    assert initiation.attempt_status == PaymentAttemptStatuses.SUCCEEDED
    assert initiation.provider_payment_id == "fake-pay-payment-1"
    assert initiation.provider_attempt_id == "fake-attempt-payment-1"
    assert initiation.redirect_url == "https://payments.example.test/fake/fake-pay-payment-1"
    assert initiation.client_payload == {
        "mode": "fake_redirect",
        "payment_reference": "fake-pay-payment-1",
    }
    assert initiation.reused is False
    assert payment_repository.created_count == 1
    assert len(attempts.attempts) == 1

    provider_request = provider.create_requests[0]
    assert provider_request.external_order_reference == "order-order-1"
    assert provider_request.description == "Cinema Showcase order order-1"
    assert provider_request.metadata == {
        "payment_id": "payment-1",
        "order_id": "order-1",
        "external_order_reference": "order-order-1",
        "user_id": "user-1",
        "client": {"source": "profile"},
    }

    repeated = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="different-client-key",
    )

    assert repeated.payment_id == initiation.payment_id
    assert repeated.attempt_id == initiation.attempt_id
    assert repeated.reused is True
    assert payment_repository.created_count == 1
    assert len(attempts.attempts) == 1
    assert len(provider.create_requests) == 1


@pytest.mark.asyncio
async def test_payment_initiation_replays_same_idempotency_key_without_new_attempt() -> None:
    service, payment_repository, attempts = build_payment_service()

    first = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="idem-replay-1",
    )
    second = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="idem-replay-1",
    )

    assert second.payment_id == first.payment_id
    assert second.attempt_id == first.attempt_id
    assert second.reused is True
    assert payment_repository.created_count == 1
    assert len(attempts.attempts) == 1


@pytest.mark.asyncio
async def test_payment_initiation_reuses_concurrent_active_payment_after_create_conflict() -> None:
    payment_repository = ConcurrentCreateConflictPaymentRepository()
    provider = RecordingFakePaymentProvider()
    service, _, attempts = build_payment_service(
        payment_repository=payment_repository,
        payment_provider=provider,
    )

    initiation = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="idem-race-1",
    )

    assert initiation.payment_id == "payment-race"
    assert initiation.provider_payment_id == "fake-pay-payment-race"
    assert initiation.status == PaymentStatuses.PENDING
    assert initiation.reused is True
    assert payment_repository.created_count == 1
    assert len(attempts.attempts) == 0
    assert provider.create_requests == []


@pytest.mark.asyncio
async def test_payment_initiation_writes_safe_audit_event() -> None:
    audit_repository = FakePaymentAuditEventRepository()
    service, _, _ = build_payment_service(payment_audit_event_repository=audit_repository)

    initiation = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="idem-audit-1",
        metadata={"source": "audit_test"},
    )

    audit_events = list(audit_repository.events.values())
    assert any(event["action"] == "payment.initiated" for event in audit_events)
    initiated = next(event for event in audit_events if event["action"] == "payment.initiated")
    assert initiated["payment_id"] == initiation.payment_id
    assert initiated["order_id"] == "order-1"
    assert initiated["actor_type"] == "user"
    assert initiated["actor_id"] == "user-1"
    assert "audit_test" not in str(initiated)


@pytest.mark.asyncio
async def test_payment_initiation_creates_new_payment_after_failed_payment_without_explicit_key() -> None:
    failed_payment = {
        **build_payment("failed-payment", status=PaymentStatuses.FAILED),
        "provider": "fake",
        "idempotency_key": "failed-payment-key",
        "failure_code": "provider_unavailable",
        "failure_message": "Provider unavailable.",
    }
    service, payment_repository, attempts = build_payment_service(
        payment_repository=FakePaymentRepository([failed_payment])
    )

    initiation = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
    )

    assert initiation.payment_id == "payment-1"
    assert initiation.status == PaymentStatuses.PENDING
    assert payment_repository.created_count == 1
    assert len(payment_repository.payments) == 2
    assert len(attempts.attempts) == 1


@pytest.mark.asyncio
async def test_payment_retry_creates_new_payment_after_failed_attempt_while_reservation_active() -> None:
    failed_payment = {
        **build_payment("failed-payment", status=PaymentStatuses.FAILED),
        "provider": "fake",
        "idempotency_key": "failed-payment-key",
        "failure_code": "provider_unavailable",
        "failure_message": "Provider unavailable.",
    }
    service, payment_repository, attempts = build_payment_service(
        payment_repository=FakePaymentRepository([failed_payment])
    )

    initiation = await service.retry_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="retry-key-1",
    )

    assert initiation.payment_id == "payment-1"
    assert initiation.status == PaymentStatuses.PENDING
    assert initiation.reused is False
    assert payment_repository.created_count == 1
    assert len(payment_repository.payments) == 2
    assert len(attempts.attempts) == 1


@pytest.mark.asyncio
async def test_payment_retry_rejects_reused_idempotency_key_without_creating_payment() -> None:
    failed_payment = {
        **build_payment("failed-payment", status=PaymentStatuses.FAILED),
        "provider": "fake",
        "idempotency_key": "retry-key-used",
    }
    service, payment_repository, attempts = build_payment_service(
        payment_repository=FakePaymentRepository([failed_payment])
    )

    with pytest.raises(ConflictException, match="idempotency key is already used"):
        await service.retry_order_payment(
            order_id="order-1",
            current_user=build_user(),
            idempotency_key="retry-key-used",
        )

    assert payment_repository.created_count == 0
    assert len(payment_repository.payments) == 1
    assert attempts.attempts == {}


@pytest.mark.asyncio
async def test_payment_retry_rejects_active_completed_expired_and_non_retry_orders() -> None:
    active_service, _, _ = build_payment_service(
        payment_repository=FakePaymentRepository(
            [{**build_payment("active-payment", status=PaymentStatuses.PENDING), "provider": "fake"}]
        )
    )
    with pytest.raises(ConflictException, match="active payment"):
        await active_service.retry_order_payment(order_id="order-1", current_user=build_user())

    no_failure_service, _, _ = build_payment_service()
    with pytest.raises(ConflictException, match="does not have"):
        await no_failure_service.retry_order_payment(order_id="order-1", current_user=build_user())

    expired_order_service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.EXPIRED),
        payment_repository=FakePaymentRepository(
            [{**build_payment("expired-payment", status=PaymentStatuses.EXPIRED), "provider": "fake"}]
        ),
    )
    with pytest.raises(ConflictException, match="Expired orders"):
        await expired_order_service.retry_order_payment(order_id="order-1", current_user=build_user())

    completed_order_service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.COMPLETED),
        payment_repository=FakePaymentRepository(
            [{**build_payment("succeeded-payment", status=PaymentStatuses.SUCCEEDED), "provider": "fake"}]
        ),
    )
    with pytest.raises(ConflictException, match="already paid"):
        await completed_order_service.retry_order_payment(order_id="order-1", current_user=build_user())


@pytest.mark.asyncio
async def test_payment_initiation_rejects_missing_non_payable_and_foreign_orders() -> None:
    missing_service = PaymentService(
        payment_repository=FakePaymentRepository(),
        payment_attempt_repository=FakePaymentAttemptRepository(),
        payment_webhook_event_repository=FakePaymentWebhookEventRepository(),
        refund_repository=FakeRefundRepository(),
        order_repository=FakeOrderRepository([]),
        ticket_repository=FakeTicketRepository(),
        session_repository=FakeSessionRepository(),
        payment_provider=FakePaymentProvider(),
    )
    with pytest.raises(NotFoundException, match="Order was not found"):
        await missing_service.initiate_order_payment(
            order_id="missing-order",
            current_user=build_user(),
        )

    completed_service, _, _ = build_payment_service(order=build_order(status=OrderStatuses.COMPLETED))
    with pytest.raises(ConflictException, match="already paid"):
        await completed_service.initiate_order_payment(
            order_id="order-1",
            current_user=build_user(),
        )

    foreign_service, _, _ = build_payment_service()
    with pytest.raises(AuthorizationException, match="own orders"):
        await foreign_service.initiate_order_payment(
            order_id="order-1",
            current_user=build_user(user_id="other-user"),
        )


@pytest.mark.asyncio
async def test_payment_details_include_safe_attempt_history() -> None:
    service, _, _ = build_payment_service()
    initiation = await service.initiate_order_payment(
        order_id="order-1",
        current_user=build_user(),
        idempotency_key="idem-details-1",
    )

    details = await service.get_payment_details(initiation.payment_id, current_user=build_user())

    assert details.id == initiation.payment_id
    assert details.status == PaymentStatuses.PENDING
    assert len(details.attempts) == 1
    assert details.attempts[0].response_payload_snapshot["provider_payment_id"] == "fake-pay-payment-1"


@pytest.mark.asyncio
async def test_payment_status_inspection_marks_active_payment_expired_for_expired_order() -> None:
    payment_repository = FakePaymentRepository(
        [{**build_payment(status=PaymentStatuses.PENDING), "provider": "fake"}]
    )
    service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.EXPIRED),
        payment_repository=payment_repository,
    )

    details = await service.get_order_payment_details("order-1", current_user=build_user())

    assert details.status == PaymentStatuses.EXPIRED
    assert payment_repository.payments["payment-1"]["failure_code"] == "reservation_expired"


@pytest.mark.asyncio
async def test_refresh_payment_status_applies_provider_truth_and_requires_provider_reference() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=10000,
            )
        ]
    )
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        payment_provider=FakePaymentProvider(default_create_raw_status="paid"),
    )

    refreshed = await service.refresh_payment_status("payment-1")

    assert refreshed.status == PaymentStatuses.SUCCEEDED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED

    missing_reference_service, _, _ = build_payment_service(
        payment_repository=FakePaymentRepository(
            [build_payment("local-only", status=PaymentStatuses.PENDING, provider="fake", provider_payment_id=None)]
        )
    )
    with pytest.raises(ConflictException, match="not been created with a provider"):
        await missing_reference_service.refresh_payment_status("local-only")


@pytest.mark.asyncio
async def test_admin_payment_details_aggregate_attempts_refunds_webhooks_and_booking_context() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=10000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    refund_repository.refunds["refund-1"] = {
        "id": "refund-1",
        "payment_id": "payment-1",
        "order_id": "order-1",
        "user_id": "user-1",
        "amount_minor": 3000,
        "currency": "UAH",
        "status": RefundStatuses.SUCCEEDED,
        "provider": "fake",
        "provider_refund_id": "fake-refund-1",
        "reason": "customer_request",
        "requested_by": "admin-1",
        "request_payload_snapshot": {"operation": "refund_payment"},
        "response_payload_snapshot": {"status": RefundStatuses.SUCCEEDED},
        "failure_code": None,
        "failure_message": None,
        "created_at": datetime.now(tz=timezone.utc),
        "updated_at": None,
    }
    webhook_events = FakePaymentWebhookEventRepository()
    await webhook_events.create_event(
        {
            "provider": "fake",
            "provider_event_id": "evt-paid-1",
            "event_type": "payment.updated",
            "signature_verified": True,
            "payload_hash": "a" * 64,
            "payload_snapshot": {"payment": {"id": "fake-pay-payment-1"}},
            "processing_status": PaymentWebhookProcessingStatuses.PROCESSED,
            "processed_at": datetime.now(tz=timezone.utc),
            "error_message": None,
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": None,
        }
    )
    tickets = FakeTicketRepository([build_reserved_ticket(status=TicketStatuses.PURCHASED)])
    service, _, attempts = build_payment_service(
        order=build_order(status=OrderStatuses.COMPLETED, expires_at=None),
        payment_repository=payment_repository,
        payment_webhook_event_repository=webhook_events,
        refund_repository=refund_repository,
        ticket_repository=tickets,
    )
    attempts.attempts["attempt-1"] = {
        "id": "attempt-1",
        "payment_id": "payment-1",
        "order_id": "order-1",
        "provider": "fake",
        "provider_attempt_id": "fake-attempt-1",
        "request_payload_snapshot": {"operation": "create_payment"},
        "response_payload_snapshot": {"status": PaymentStatuses.SUCCEEDED},
        "status": PaymentAttemptStatuses.SUCCEEDED,
        "error_code": None,
        "error_message": None,
        "created_at": datetime.now(tz=timezone.utc),
        "updated_at": None,
    }

    payments = await service.list_admin_payments(search="fake-pay-payment-1")
    details = await service.get_admin_payment_details("payment-1")

    assert payments[0].attempts_count == 1
    assert payments[0].refunds_count == 1
    assert payments[0].refunded_amount_minor == 3000
    assert payments[0].remaining_refundable_amount_minor == 7000
    assert payments[0].refundable is True
    assert details.attempts[0].id == "attempt-1"
    assert details.refunds[0].id == "refund-1"
    assert details.webhook_events[0].provider_event_id == "evt-paid-1"
    assert details.order is not None
    assert details.order.seats == ["1-1"]


@pytest.mark.asyncio
async def test_admin_payment_report_counts_revenue_refunds_and_booking_aggregates() -> None:
    now = datetime.now(tz=timezone.utc)
    date_from = now - timedelta(days=1)
    date_to = now + timedelta(days=1)
    old_date = now - timedelta(days=5)
    future_date = now + timedelta(hours=1)

    payment_repository = FakePaymentRepository(
        [
            build_payment(
                "payment-success-1",
                order_id="order-paid-1",
                amount_minor=10000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                created_at=now,
            ),
            {
                **build_payment(
                    "payment-failed-1",
                    order_id="order-failed-1",
                    amount_minor=5000,
                    status=PaymentStatuses.FAILED,
                    provider="fake",
                    created_at=now,
                ),
                "failure_code": "card_declined",
            },
            build_payment(
                "payment-pending-1",
                order_id="order-pending-1",
                amount_minor=7000,
                status=PaymentStatuses.PENDING,
                provider="fake",
                created_at=now,
            ),
            build_payment(
                "payment-partial-1",
                order_id="order-paid-2",
                amount_minor=8000,
                status=PaymentStatuses.PARTIALLY_REFUNDED,
                provider="fake",
                created_at=now,
            ),
            build_payment(
                "payment-old-1",
                order_id="order-old-1",
                amount_minor=9000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                created_at=old_date,
            ),
        ]
    )
    refund_repository = FakeRefundRepository(
        [
            build_refund(
                "refund-success-1",
                payment_id="payment-success-1",
                order_id="order-paid-1",
                amount_minor=3000,
                created_at=future_date,
            ),
            build_refund(
                "refund-success-2",
                payment_id="payment-partial-1",
                order_id="order-paid-2",
                amount_minor=2000,
                created_at=future_date,
            ),
            build_refund(
                "refund-failed-1",
                payment_id="payment-success-1",
                order_id="order-paid-1",
                amount_minor=999,
                status=RefundStatuses.FAILED,
                created_at=future_date,
            ),
            build_refund(
                "refund-old-1",
                payment_id="payment-success-1",
                order_id="order-paid-1",
                amount_minor=1000,
                created_at=old_date,
            ),
        ]
    )
    order_repository = FakeOrderRepository(
        [
            build_order("order-paid-1", status=OrderStatuses.COMPLETED, session_id="session-1", tickets_count=2),
            build_order("order-paid-2", status=OrderStatuses.COMPLETED, session_id="session-2", tickets_count=3),
            build_order("order-failed-1", status=OrderStatuses.PAYMENT_FAILED, session_id="session-1", tickets_count=1),
            build_order("order-pending-1", status=OrderStatuses.PENDING_PAYMENT, session_id="session-2", tickets_count=1),
            build_order("order-old-1", status=OrderStatuses.COMPLETED, session_id="session-1", tickets_count=4),
        ]
    )
    session_repository = FakeSessionRepository(
        [
            {
                "id": "session-1",
                "movie_id": "movie-1",
                "start_time": now + timedelta(days=1),
                "end_time": now + timedelta(days=1, hours=2),
                "price": 50,
                "status": "scheduled",
                "total_seats": 96,
                "available_seats": 94,
                "created_at": now,
                "updated_at": None,
            },
            {
                "id": "session-2",
                "movie_id": "movie-2",
                "start_time": now + timedelta(days=2),
                "end_time": now + timedelta(days=2, hours=2),
                "price": 80,
                "status": "scheduled",
                "total_seats": 96,
                "available_seats": 93,
                "created_at": now,
                "updated_at": None,
            },
        ]
    )
    service = PaymentService(
        payment_repository=payment_repository,
        payment_attempt_repository=FakePaymentAttemptRepository(),
        payment_webhook_event_repository=FakePaymentWebhookEventRepository(),
        refund_repository=refund_repository,
        order_repository=order_repository,
        ticket_repository=FakeTicketRepository(),
        session_repository=session_repository,
        payment_provider=FakePaymentProvider(),
        movie_repository=FakeMovieRepository(
            [
                {"id": "movie-1", "title": {"uk": "Movie 1", "en": "Movie 1"}},
                {"id": "movie-2", "title": {"uk": "Movie 2", "en": "Movie 2"}},
            ]
        ),
    )

    report = await service.get_admin_payment_report(date_from=date_from, date_to=date_to)

    assert report.period.payment_timestamp_basis == "payment.created_at"
    assert report.period.refund_timestamp_basis == "refund.created_at"
    assert report.summary.total_payments_count == 4
    assert report.summary.succeeded_payments_count == 2
    assert report.summary.failed_payments_count == 1
    assert report.summary.pending_payments_count == 1
    assert report.summary.partially_refunded_payments_count == 1
    assert report.summary.gross_revenue_minor == 18000
    assert report.summary.refunded_amount_minor == 5000
    assert report.summary.net_revenue_minor == 13000
    assert report.summary.succeeded_orders_count == 2
    assert report.summary.paid_tickets_count == 5
    assert report.summary.success_rate == pytest.approx(0.5)

    sessions_by_id = {session.session_id: session for session in report.sessions}
    assert sessions_by_id["session-1"].gross_revenue_minor == 10000
    assert sessions_by_id["session-1"].refunded_amount_minor == 3000
    assert sessions_by_id["session-1"].net_revenue_minor == 7000
    assert sessions_by_id["session-1"].paid_tickets_count == 2
    assert sessions_by_id["session-2"].gross_revenue_minor == 8000
    assert sessions_by_id["session-2"].refunded_amount_minor == 2000
    assert sessions_by_id["session-2"].paid_tickets_count == 3

    movies_by_id = {movie.movie_id: movie for movie in report.movies}
    assert movies_by_id["movie-1"].movie_title is not None
    assert movies_by_id["movie-1"].movie_title.en == "Movie 1"
    assert movies_by_id["movie-1"].net_revenue_minor == 7000
    assert movies_by_id["movie-2"].gross_revenue_minor == 8000
    assert movies_by_id["movie-2"].paid_sessions_count == 1


@pytest.mark.asyncio
async def test_payment_service_rejects_idempotency_key_reuse_for_another_order() -> None:
    payment_repository = FakePaymentRepository(
        [{**build_payment(), "status": PaymentStatuses.CREATED, "idempotency_key": "shared-key-1"}]
    )
    service, _, _ = build_payment_service(
        order=build_order("order-2"),
        payment_repository=payment_repository,
    )

    with pytest.raises(ConflictException, match="another order"):
        await service.create_payment_for_order(
            order_id="order-2",
            idempotency_key="shared-key-1",
        )


@pytest.mark.asyncio
async def test_payment_service_rejects_provider_override_that_differs_from_configured_provider() -> None:
    service, _, _ = build_payment_service()

    with pytest.raises(ConflictException, match="configured provider"):
        await service.create_payment_for_order(
            order_id="order-1",
            provider="other-provider",
            idempotency_key="idem-order-1",
        )


@pytest.mark.asyncio
async def test_payment_service_marks_local_records_failed_when_provider_creation_fails() -> None:
    service, payment_repository, attempts = build_payment_service(
        payment_provider=FailingCreatePaymentProvider()
    )

    with pytest.raises(ConflictException, match="failed to create payment"):
        await service.create_payment_for_order(
            order_id="order-1",
            idempotency_key="idem-order-1",
        )

    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.FAILED
    assert payment_repository.payments["payment-1"]["failure_code"] == "provider_unavailable"
    assert attempts.attempts["attempt-1"]["status"] == PaymentAttemptStatuses.FAILED
    assert attempts.attempts["attempt-1"]["error_code"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_payment_service_cancel_flow_calls_provider_and_persists_normalized_status() -> None:
    service, _, _ = build_payment_service()
    payment = await service.create_payment_for_order(
        order_id="order-1",
        idempotency_key="idem-order-1",
    )

    cancelled = await service.cancel_payment(payment.id, reason="customer_request")

    assert cancelled.status == PaymentStatuses.CANCELLED
    assert cancelled.provider_payment_id == "fake-pay-payment-1"


@pytest.mark.asyncio
async def test_payment_service_refund_flow_calls_provider_and_refreshes_payment_status() -> None:
    refund_repository = FakeRefundRepository()
    service, payment_repository, _ = build_payment_service(
        refund_repository=refund_repository,
        payment_provider=FakePaymentProvider(default_create_raw_status="paid"),
    )
    payment = await service.create_payment_for_order(
        order_id="order-1",
        idempotency_key="idem-order-1",
    )

    refund = await service.refund_payment(
        payment_id=payment.id,
        amount_minor=2345,
        reason="customer_request",
    )

    assert refund.status == RefundStatuses.SUCCEEDED
    assert refund.provider_refund_id == "fake-refund-refund-1"
    assert payment_repository.payments[payment.id]["status"] == PaymentStatuses.PARTIALLY_REFUNDED
    assert refund.user_id == "user-1"
    assert refund.requested_by == "system"
    assert refund_repository.refunds[refund.id]["response_payload_snapshot"]["status"] == RefundStatuses.SUCCEEDED


@pytest.mark.asyncio
async def test_customer_ticket_refund_request_creates_partial_refund_for_cancelled_ticket() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=20000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    tickets = FakeTicketRepository(
        [
            build_reserved_ticket(
                "ticket-1",
                price=123.45,
                status=TicketStatuses.CANCELLED,
                seat_number=1,
            ),
            build_reserved_ticket(
                "ticket-2",
                price=76.55,
                status=TicketStatuses.PURCHASED,
                seat_number=2,
            ),
        ]
    )
    service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.PARTIALLY_CANCELLED, expires_at=None, tickets_count=2),
        payment_repository=payment_repository,
        refund_repository=refund_repository,
        ticket_repository=tickets,
        payment_provider=FakePaymentProvider(),
    )

    result = await service.request_order_refund(
        order_id="order-1",
        payload=CustomerRefundRequest(scope="tickets", ticket_ids=["ticket-1"]),
        current_user=build_user(),
    )

    assert result.refund.amount_minor == 12345
    assert result.refund.status == RefundStatuses.SUCCEEDED
    assert result.refund.reason == "customer_cancelled_ticket"
    assert result.refund.request_payload_snapshot["metadata"]["scope"] == "tickets"
    assert result.refund.request_payload_snapshot["metadata"]["ticket_ids"] == ["ticket-1"]
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.PARTIALLY_REFUNDED
    assert result.remaining_refundable_amount_minor == 7655


@pytest.mark.asyncio
async def test_customer_full_order_refund_requires_cancelled_order_and_refunds_remaining_amount() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=20000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    tickets = FakeTicketRepository(
        [
            build_reserved_ticket("ticket-1", price=120.0, status=TicketStatuses.CANCELLED, seat_number=1),
            build_reserved_ticket("ticket-2", price=80.0, status=TicketStatuses.CANCELLED, seat_number=2),
        ]
    )
    service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.CANCELLED, expires_at=None, tickets_count=2),
        payment_repository=payment_repository,
        ticket_repository=tickets,
        payment_provider=FakePaymentProvider(),
    )

    result = await service.request_order_refund(
        order_id="order-1",
        payload=CustomerRefundRequest(scope="order"),
        current_user=build_user(),
    )

    assert result.refund.amount_minor == 20000
    assert result.refund.request_payload_snapshot["metadata"]["scope"] == "order"
    assert sorted(result.refund.request_payload_snapshot["metadata"]["ticket_ids"]) == ["ticket-1", "ticket-2"]
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.REFUNDED
    assert result.remaining_refundable_amount_minor == 0


@pytest.mark.asyncio
async def test_customer_refund_request_rejects_foreign_order_active_ticket_duplicate_and_over_refund() -> None:
    base_payment = build_payment(
        amount_minor=10000,
        status=PaymentStatuses.SUCCEEDED,
        provider="fake",
        provider_payment_id="fake-pay-payment-1",
    )

    foreign_service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.CANCELLED, user_id="other-user", expires_at=None),
        payment_repository=FakePaymentRepository([base_payment]),
        ticket_repository=FakeTicketRepository([build_reserved_ticket(status=TicketStatuses.CANCELLED)]),
    )
    with pytest.raises(AuthorizationException, match="own orders"):
        await foreign_service.request_order_refund(
            order_id="order-1",
            payload=CustomerRefundRequest(scope="tickets", ticket_ids=["ticket-1"]),
            current_user=build_user(),
        )

    active_service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.COMPLETED, expires_at=None),
        payment_repository=FakePaymentRepository([base_payment]),
        ticket_repository=FakeTicketRepository([build_reserved_ticket(status=TicketStatuses.PURCHASED)]),
    )
    with pytest.raises(ConflictException, match="Only cancelled tickets"):
        await active_service.request_order_refund(
            order_id="order-1",
            payload=CustomerRefundRequest(scope="tickets", ticket_ids=["ticket-1"]),
            current_user=build_user(),
        )
    with pytest.raises(ConflictException, match="Cancel all active tickets"):
        await active_service.request_order_refund(
            order_id="order-1",
            payload=CustomerRefundRequest(scope="order"),
            current_user=build_user(),
        )

    duplicate_refund = build_refund(
        amount_minor=5000,
        status=RefundStatuses.PENDING,
    )
    duplicate_refund["request_payload_snapshot"] = {
        "operation": "refund_payment",
        "metadata": {"ticket_ids": ["ticket-1"]},
    }
    duplicate_service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.CANCELLED, expires_at=None),
        payment_repository=FakePaymentRepository([base_payment]),
        refund_repository=FakeRefundRepository([duplicate_refund]),
        ticket_repository=FakeTicketRepository([build_reserved_ticket(status=TicketStatuses.CANCELLED)]),
    )
    with pytest.raises(ConflictException, match="already been requested"):
        await duplicate_service.request_order_refund(
            order_id="order-1",
            payload=CustomerRefundRequest(scope="tickets", ticket_ids=["ticket-1"]),
            current_user=build_user(),
        )

    reserved_refund = build_refund("refund-reserved", amount_minor=9000, status=RefundStatuses.CREATED)
    over_refund_service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.CANCELLED, expires_at=None),
        payment_repository=FakePaymentRepository([base_payment]),
        refund_repository=FakeRefundRepository([reserved_refund]),
        ticket_repository=FakeTicketRepository(
            [build_reserved_ticket(status=TicketStatuses.CANCELLED, price=20.0)]
        ),
    )
    with pytest.raises(ConflictException, match="exceeds the remaining"):
        await over_refund_service.request_order_refund(
            order_id="order-1",
            payload=CustomerRefundRequest(scope="tickets", ticket_ids=["ticket-1"]),
            current_user=build_user(),
        )


@pytest.mark.asyncio
async def test_refund_service_provider_backed_partial_and_full_refunds_accumulate() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=10000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    provider = RecordingFakePaymentProvider()
    service = RefundService(
        refund_repository=refund_repository,
        payment_repository=payment_repository,
        payment_provider=provider,
    )

    partial = await service.refund_payment(
        payment_id="payment-1",
        amount_minor=3000,
        reason="customer_request",
        requested_by="admin-1",
        metadata={"source": "admin_test"},
    )
    full_remainder = await service.refund_payment(
        payment_id="payment-1",
        amount_minor=None,
        reason="session_cancelled",
        requested_by="admin-1",
    )

    assert partial.status == RefundStatuses.SUCCEEDED
    assert full_remainder.amount_minor == 7000
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.REFUNDED
    assert [request.amount_minor for request in provider.refund_requests] == [3000, 7000]
    assert refund_repository.refunds[partial.id]["request_payload_snapshot"]["metadata"] == {"source": "admin_test"}


@pytest.mark.asyncio
async def test_refund_service_counts_created_pending_and_succeeded_refunds_as_reserved_amounts() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=10000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository(
        [
            build_refund("refund-created", amount_minor=3000, status=RefundStatuses.CREATED),
            build_refund("refund-pending", amount_minor=4000, status=RefundStatuses.PENDING),
        ]
    )
    service = RefundService(
        refund_repository=refund_repository,
        payment_repository=payment_repository,
    )

    assert await service.get_remaining_refundable_amount("payment-1") == 3000
    with pytest.raises(ConflictException, match="exceeds"):
        await service.create_refund(
            payment_id="payment-1",
            amount_minor=3001,
            reason="admin_adjustment",
        )

    final_reserved = await service.create_refund(
        payment_id="payment-1",
        amount_minor=3000,
        reason="admin_adjustment",
    )
    assert final_reserved.status == RefundStatuses.CREATED
    assert await service.get_remaining_refundable_amount("payment-1") == 0


@pytest.mark.asyncio
async def test_refund_status_transitions_and_audit_reject_terminal_reopen() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=5000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    audit_repository = FakePaymentAuditEventRepository()
    service = RefundService(
        refund_repository=refund_repository,
        payment_repository=payment_repository,
        payment_audit_event_repository=audit_repository,
    )

    refund = await service.create_refund(
        payment_id="payment-1",
        amount_minor=2000,
        reason="customer_request",
        requested_by="admin:user-1",
    )
    pending = await service.mark_refund_pending(refund.id, provider_refund_id="fake-refund-refund-1")
    failed = await service.mark_refund_failed(
        pending.id,
        failure_code="provider_refund_failed",
        failure_message="Provider rejected the refund.",
    )

    with pytest.raises(ConflictException, match="Refund cannot move"):
        await service.mark_refund_succeeded(failed.id)

    audit_actions = [event["action"] for event in audit_repository.events.values()]
    assert audit_actions.count("refund.created") == 1
    assert audit_actions.count("refund.status_changed") == 2
    created_audit = next(event for event in audit_repository.events.values() if event["action"] == "refund.created")
    assert created_audit["actor_type"] == "admin"
    assert created_audit["actor_id"] == "admin:user-1"
    failed_audit = next(event for event in audit_repository.events.values() if event.get("new_status") == RefundStatuses.FAILED)
    assert failed_audit["reason"] == "provider_refund_failed"


@pytest.mark.asyncio
async def test_refund_provider_result_mismatch_is_rejected_before_local_state_changes() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=5000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    service = RefundService(
        refund_repository=refund_repository,
        payment_repository=payment_repository,
        payment_provider=FakePaymentProvider(),
    )
    refund = await service.create_refund(
        payment_id="payment-1",
        amount_minor=2000,
        reason="customer_request",
    )

    with pytest.raises(ConflictException, match="amount does not match"):
        await service.apply_provider_result(
            refund.id,
            ProviderRefundResult(
                provider="fake",
                provider_refund_id="fake-refund-mismatch",
                status=RefundStatuses.SUCCEEDED,
                amount_minor=2500,
                currency="UAH",
            ),
        )

    assert refund_repository.refunds[refund.id]["status"] == RefundStatuses.CREATED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED


@pytest.mark.asyncio
async def test_refund_service_provider_failure_records_failed_refund_without_payment_refund_status() -> None:
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=10000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    service = RefundService(
        refund_repository=refund_repository,
        payment_repository=payment_repository,
        payment_provider=FailingRefundPaymentProvider(),
    )

    failed = await service.refund_payment(
        payment_id="payment-1",
        amount_minor=2000,
        reason="customer_request",
        requested_by="admin-1",
        fail_on_provider_error=False,
    )
    with pytest.raises(ConflictException, match="Payment provider failed"):
        await service.refund_payment(
            payment_id="payment-1",
            amount_minor=2000,
            reason="customer_request",
            requested_by="admin-1",
        )

    assert failed.status == RefundStatuses.FAILED
    assert failed.failure_code == "refund_provider_unavailable"
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED
    assert len(refund_repository.refunds) == 2


@pytest.mark.asyncio
async def test_refund_webhook_updates_refund_and_payment_aggregate(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                amount_minor=10000,
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
            )
        ]
    )
    refund_repository = FakeRefundRepository()
    await refund_repository.create_refund(
        {
            "payment_id": "payment-1",
            "order_id": "order-1",
            "user_id": "user-1",
            "amount_minor": 10000,
            "currency": "UAH",
            "status": RefundStatuses.PENDING,
            "provider": "fake",
            "provider_refund_id": "fake-refund-refund-1",
            "reason": "session_cancelled",
            "requested_by": "admin-1",
            "request_payload_snapshot": None,
            "response_payload_snapshot": None,
            "failure_code": None,
            "failure_message": None,
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": None,
        }
    )
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        refund_repository=refund_repository,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-refund-1",
            "event_type": "refund.updated",
            "refund": {
                "id": "fake-refund-refund-1",
                "status": "refund_settled",
                "amount_minor": 10000,
                "currency": "UAH",
            },
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert result.payment_id == "payment-1"
    assert result.refund_id == "refund-1"
    assert refund_repository.refunds["refund-1"]["status"] == RefundStatuses.SUCCEEDED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.REFUNDED


@pytest.mark.asyncio
async def test_successful_payment_webhook_updates_payment_finalizes_order_and_is_idempotent(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    webhook_events = FakePaymentWebhookEventRepository()
    tickets = FakeTicketRepository([build_reserved_ticket()])
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        payment_webhook_event_repository=webhook_events,
        ticket_repository=tickets,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-paid-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "paid",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )
    duplicate = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )
    changed_raw_body, changed_signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-paid-1",
            "event_type": "payment.updated",
            "extra": "changed-payload",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "paid",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert result.payment_id == "payment-1"
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED
    assert service.order_repository.orders["order-1"]["status"] == OrderStatuses.COMPLETED
    assert tickets.tickets[0]["status"] == TicketStatuses.PURCHASED
    assert tickets.tickets[0]["purchased_at"] is not None
    assert duplicate.duplicate is True
    assert duplicate.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert webhook_events.created_count == 1
    with pytest.raises(ConflictException, match="different payload"):
        await service.process_provider_webhook(
            raw_body=changed_raw_body,
            headers={"x-fake-payment-signature": changed_signature},
        )


@pytest.mark.asyncio
async def test_payment_webhook_without_provider_event_id_deduplicates_by_payload_hash(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    webhook_events = FakePaymentWebhookEventRepository()
    tickets = FakeTicketRepository([build_reserved_ticket()])
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        payment_webhook_event_repository=webhook_events,
        ticket_repository=tickets,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "paid",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    first = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )
    duplicate = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert first.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert first.provider_event_id.startswith("payload-")
    assert duplicate.duplicate is True
    assert webhook_events.created_count == 1
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED
    assert tickets.tickets[0]["status"] == TicketStatuses.PURCHASED


@pytest.mark.asyncio
async def test_stale_terminal_payment_webhook_is_skipped_without_releasing_booking(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.SUCCEEDED,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    webhook_events = FakePaymentWebhookEventRepository()
    audit_events = FakePaymentAuditEventRepository()
    tickets = FakeTicketRepository([build_reserved_ticket(status=TicketStatuses.PURCHASED)])
    sessions = FakeSessionRepository()
    service, _, _ = build_payment_service(
        order=build_order(status=OrderStatuses.COMPLETED, expires_at=None),
        payment_repository=payment_repository,
        payment_webhook_event_repository=webhook_events,
        payment_audit_event_repository=audit_events,
        ticket_repository=tickets,
        session_repository=sessions,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-stale-failed-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "declined",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.SKIPPED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED
    assert service.order_repository.orders["order-1"]["status"] == OrderStatuses.COMPLETED
    assert tickets.tickets[0]["status"] == TicketStatuses.PURCHASED
    assert sessions.restored_quantity == 0
    event = next(iter(webhook_events.events.values()))
    assert event["processing_status"] == PaymentWebhookProcessingStatuses.SKIPPED
    audit = next(event for event in audit_events.events.values() if event["action"] == "webhook.skipped")
    assert audit["old_status"] == PaymentStatuses.SUCCEEDED
    assert audit["new_status"] == PaymentStatuses.FAILED
    assert audit["reason"] == "stale_payment_transition"


@pytest.mark.asyncio
async def test_verified_webhook_without_payment_or_refund_is_stored_and_skipped_safely(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    webhook_events = FakePaymentWebhookEventRepository()
    audit_events = FakePaymentAuditEventRepository()
    service, _, _ = build_payment_service(
        payment_webhook_event_repository=webhook_events,
        payment_audit_event_repository=audit_events,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-empty-1",
            "event_type": "provider.ping",
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.SKIPPED
    assert result.payment_id is None
    event = next(iter(webhook_events.events.values()))
    assert event["processing_status"] == PaymentWebhookProcessingStatuses.SKIPPED
    assert event["error_message"] == "Webhook event does not contain payment data."
    audit = next(iter(audit_events.events.values()))
    assert audit["action"] == "webhook.skipped"
    assert audit["reason"] == "missing_payment_data"
    assert audit["payment_id"] is None


@pytest.mark.asyncio
async def test_webhook_for_unknown_provider_payment_marks_event_failed_without_local_mutation(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    webhook_events = FakePaymentWebhookEventRepository()
    service, payment_repository, _ = build_payment_service(
        payment_webhook_event_repository=webhook_events,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-unknown-payment-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-missing",
                "status": "paid",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    with pytest.raises(NotFoundException, match="Payment for this webhook event was not found"):
        await service.process_provider_webhook(
            raw_body=raw_body,
            headers={"x-fake-payment-signature": signature},
        )

    event = next(iter(webhook_events.events.values()))
    assert event["processing_status"] == PaymentWebhookProcessingStatuses.FAILED
    assert "not found" in event["error_message"]
    assert payment_repository.payments == {}


@pytest.mark.asyncio
async def test_failed_payment_webhook_marks_payment_and_releases_reserved_order(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    webhook_events = FakePaymentWebhookEventRepository()
    tickets = FakeTicketRepository([build_reserved_ticket()])
    sessions = FakeSessionRepository()
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        payment_webhook_event_repository=webhook_events,
        ticket_repository=tickets,
        session_repository=sessions,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-failed-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "declined",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.FAILED
    assert payment_repository.payments["payment-1"]["failure_code"] == "fake_declined"
    assert tickets.tickets[0]["status"] == TicketStatuses.EXPIRED
    assert service.order_repository.orders["order-1"]["status"] == OrderStatuses.PAYMENT_FAILED
    assert sessions.session["available_seats"] == 96
    assert sessions.restored_quantity == 1
    assert next(iter(webhook_events.events.values()))["processing_status"] == PaymentWebhookProcessingStatuses.PROCESSED


@pytest.mark.asyncio
async def test_cancelled_payment_webhook_cancels_pending_order_and_restores_seat(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    tickets = FakeTicketRepository([build_reserved_ticket()])
    sessions = FakeSessionRepository()
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        ticket_repository=tickets,
        session_repository=sessions,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-cancelled-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "voided",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.CANCELLED
    assert tickets.tickets[0]["status"] == TicketStatuses.CANCELLED
    assert tickets.tickets[0]["cancelled_at"] is not None
    assert service.order_repository.orders["order-1"]["status"] == OrderStatuses.PAYMENT_CANCELLED
    assert sessions.session["available_seats"] == 96


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "payment_status", "order_status", "ticket_status", "restored_quantity"),
    [
        ("succeeded", PaymentStatuses.SUCCEEDED, OrderStatuses.COMPLETED, TicketStatuses.PURCHASED, 0),
        ("failed", PaymentStatuses.FAILED, OrderStatuses.PAYMENT_FAILED, TicketStatuses.EXPIRED, 1),
        ("cancelled", PaymentStatuses.CANCELLED, OrderStatuses.PAYMENT_CANCELLED, TicketStatuses.CANCELLED, 1),
        ("pending", PaymentStatuses.PENDING, OrderStatuses.PENDING_PAYMENT, TicketStatuses.RESERVED, 0),
    ],
)
async def test_demo_payment_simulation_uses_signed_webhook_lifecycle(
    monkeypatch,
    result: str,
    payment_status: str,
    order_status: str,
    ticket_status: str,
    restored_quantity: int,
) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    webhook_events = FakePaymentWebhookEventRepository()
    tickets = FakeTicketRepository([build_reserved_ticket()])
    sessions = FakeSessionRepository()
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        payment_webhook_event_repository=webhook_events,
        ticket_repository=tickets,
        session_repository=sessions,
    )

    simulation = await service.simulate_fake_provider_payment(
        "payment-1",
        result=result,
        current_user=build_user(),
    )

    assert simulation.result == result
    assert simulation.webhook.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert simulation.payment.status == payment_status
    assert payment_repository.payments["payment-1"]["status"] == payment_status
    assert service.order_repository.orders["order-1"]["status"] == order_status
    assert tickets.tickets[0]["status"] == ticket_status
    assert sessions.restored_quantity == restored_quantity
    event = next(iter(webhook_events.events.values()))
    assert event["signature_verified"] is True
    assert event["payload_snapshot"]["demo_simulation"]["source"] == "local_fake_payment_page"


@pytest.mark.asyncio
async def test_demo_payment_simulation_is_disabled_outside_demo_environments(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.payment.get_settings",
        lambda: Settings(environment="production", payment_provider="fake"),
    )
    service, _, _ = build_payment_service(
        payment_repository=FakePaymentRepository(
            [
                build_payment(
                    status=PaymentStatuses.PENDING,
                    provider="fake",
                    provider_payment_id="fake-pay-payment-1",
                )
            ]
        )
    )

    with pytest.raises(AuthorizationException, match="disabled outside development or demo"):
        await service.simulate_fake_provider_payment(
            "payment-1",
            result="succeeded",
            current_user=build_user(),
        )


@pytest.mark.asyncio
async def test_expired_payment_webhook_expires_payment_order_and_restores_seat(monkeypatch) -> None:
    monkeypatch.setattr("app.services.payment.run_transaction_with_retry", run_without_real_transaction)
    payment_repository = FakePaymentRepository(
        [
            build_payment(
                status=PaymentStatuses.PENDING,
                provider="fake",
                provider_payment_id="fake-pay-payment-1",
                amount_minor=12345,
            )
        ]
    )
    tickets = FakeTicketRepository([build_reserved_ticket()])
    sessions = FakeSessionRepository()
    service, _, _ = build_payment_service(
        payment_repository=payment_repository,
        ticket_repository=tickets,
        session_repository=sessions,
    )
    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-expired-1",
            "event_type": "payment.updated",
            "payment": {
                "id": "fake-pay-payment-1",
                "status": "expired",
                "amount_minor": 12345,
                "currency": "UAH",
            },
        }
    )

    result = await service.process_provider_webhook(
        raw_body=raw_body,
        headers={"x-fake-payment-signature": signature},
    )

    assert result.processing_status == PaymentWebhookProcessingStatuses.PROCESSED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.EXPIRED
    assert payment_repository.payments["payment-1"]["failure_code"] == "provider_payment_expired"
    assert tickets.tickets[0]["status"] == TicketStatuses.EXPIRED
    assert service.order_repository.orders["order-1"]["status"] == OrderStatuses.EXPIRED
    assert sessions.session["available_seats"] == 96


@pytest.mark.asyncio
async def test_payment_webhook_rejects_invalid_signature_and_stores_failed_audit_record() -> None:
    webhook_events = FakePaymentWebhookEventRepository()
    audit_events = FakePaymentAuditEventRepository()
    service, _, _ = build_payment_service(
        payment_webhook_event_repository=webhook_events,
        payment_audit_event_repository=audit_events,
    )
    raw_body, _ = sign_fake_webhook_payload({"event_id": "evt-bad-signature"})

    with pytest.raises(AuthenticationException, match="Invalid payment webhook signature"):
        await service.process_provider_webhook(
            raw_body=raw_body,
            headers={"x-fake-payment-signature": "bad"},
        )

    event = next(iter(webhook_events.events.values()))
    assert event["signature_verified"] is False
    assert event["processing_status"] == PaymentWebhookProcessingStatuses.FAILED
    assert event["event_type"] == "unverified"
    audit = next(iter(audit_events.events.values()))
    assert audit["action"] == "webhook.rejected_invalid_signature"
    assert audit["webhook_event_id"] == event["id"]
    assert "bad" not in str(audit)


@pytest.mark.asyncio
async def test_payment_webhook_rejects_malformed_verified_payload_and_stores_audit_record() -> None:
    webhook_events = FakePaymentWebhookEventRepository()
    audit_events = FakePaymentAuditEventRepository()
    service, _, _ = build_payment_service(
        payment_webhook_event_repository=webhook_events,
        payment_audit_event_repository=audit_events,
    )
    raw_body = b"{not-valid-json"
    signature = hmac.new(b"fake-webhook-secret", raw_body, hashlib.sha256).hexdigest()

    with pytest.raises(ValidationException, match="Malformed payment webhook payload"):
        await service.process_provider_webhook(
            raw_body=raw_body,
            headers={"x-fake-payment-signature": signature},
        )

    event = next(iter(webhook_events.events.values()))
    assert event["signature_verified"] is True
    assert event["processing_status"] == PaymentWebhookProcessingStatuses.FAILED
    assert event["event_type"] == "malformed"
    audit = next(iter(audit_events.events.values()))
    assert audit["action"] == "webhook.rejected_malformed"
    assert audit["webhook_event_id"] == event["id"]
    assert "not-valid-json" not in str(audit)


def test_payment_service_depends_on_provider_abstraction_not_fake_adapter() -> None:
    source = inspect.getsource(PaymentService)

    assert "FakePaymentProvider" not in source
    assert "stripe" not in source.lower()


@pytest.mark.asyncio
async def test_payment_status_transitions_are_explicit() -> None:
    service, _, _ = build_payment_service(
        payment_repository=FakePaymentRepository([{**build_payment(), "status": PaymentStatuses.CREATED}])
    )

    pending = await service.mark_payment_pending("payment-1")
    assert pending.status == PaymentStatuses.PENDING

    succeeded = await service.mark_payment_succeeded("payment-1", provider_payment_id="provider-pay-1")
    assert succeeded.status == PaymentStatuses.SUCCEEDED
    assert succeeded.provider_payment_id == "provider-pay-1"

    with pytest.raises(ConflictException, match="cannot move"):
        await service.mark_payment_pending("payment-1")

    expiring_service, _, _ = build_payment_service(
        payment_repository=FakePaymentRepository(
            [build_payment("payment-expiring", status=PaymentStatuses.PENDING)]
        )
    )
    expired = await expiring_service.mark_payment_expired(
        "payment-expiring",
        failure_code="reservation_expired",
        failure_message="Reservation expired.",
    )
    assert expired.status == PaymentStatuses.EXPIRED


@pytest.mark.asyncio
async def test_payment_attempt_lifecycle_records_safe_snapshots_and_errors() -> None:
    service, _, attempts = build_payment_service(
        payment_repository=FakePaymentRepository([{**build_payment(), "status": PaymentStatuses.CREATED}])
    )

    attempt = await service.create_payment_attempt(
        payment_id="payment-1",
        request_payload_snapshot={"mode": "hosted_checkout", "amount_minor": 10000},
    )
    assert attempt.payment_id == "payment-1"
    assert attempt.order_id == "order-1"
    assert attempt.status == PaymentAttemptStatuses.CREATED

    pending = await service.mark_attempt_pending(attempt.id)
    assert pending.status == PaymentAttemptStatuses.PENDING

    succeeded = await service.mark_attempt_succeeded(
        attempt.id,
        provider_attempt_id="provider-attempt-1",
        response_payload_snapshot={"provider_status": "ok"},
    )
    assert succeeded.status == PaymentAttemptStatuses.SUCCEEDED
    assert attempts.attempts[attempt.id]["provider_attempt_id"] == "provider-attempt-1"


@pytest.mark.asyncio
async def test_payment_attempt_rejects_sensitive_snapshots() -> None:
    service, _, _ = build_payment_service(
        payment_repository=FakePaymentRepository([{**build_payment(), "status": PaymentStatuses.CREATED}])
    )

    with pytest.raises(ValidationError, match="sensitive key"):
        await service.create_payment_attempt(
            payment_id="payment-1",
            request_payload_snapshot={"card_number": "4111111111111111"},
        )


@pytest.mark.asyncio
async def test_refund_service_creates_refund_and_updates_payment_aggregate_status() -> None:
    payment_repository = FakePaymentRepository([build_payment(amount_minor=10000)])
    refund_repository = FakeRefundRepository()
    service = RefundService(
        refund_repository=refund_repository,
        payment_repository=payment_repository,
    )

    first_refund = await service.create_refund(
        payment_id="payment-1",
        amount_minor=3000,
        reason="customer_request",
    )
    assert first_refund.status == RefundStatuses.CREATED
    assert first_refund.currency == "UAH"
    assert first_refund.order_id == "order-1"

    succeeded = await service.mark_refund_succeeded(first_refund.id, provider_refund_id="provider-refund-1")
    assert succeeded.status == RefundStatuses.SUCCEEDED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.PARTIALLY_REFUNDED

    second_refund = await service.create_refund(
        payment_id="payment-1",
        amount_minor=7000,
        reason="session_cancelled",
    )
    await service.mark_refund_succeeded(second_refund.id)
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.REFUNDED


@pytest.mark.asyncio
async def test_refund_service_rejects_non_succeeded_payments_and_over_refunds() -> None:
    payment_repository = FakePaymentRepository(
        [build_payment(amount_minor=10000, status=PaymentStatuses.PENDING)]
    )
    service = RefundService(
        refund_repository=FakeRefundRepository(),
        payment_repository=payment_repository,
    )

    with pytest.raises(ConflictException, match="Only succeeded payments"):
        await service.create_refund(payment_id="payment-1", amount_minor=100, reason="not_paid")

    payment_repository.payments["payment-1"]["status"] = PaymentStatuses.SUCCEEDED
    with pytest.raises(ConflictException, match="exceeds"):
        await service.create_refund(payment_id="payment-1", amount_minor=10001, reason="too_much")


@pytest.mark.parametrize(
    "schema_factory",
    [
        lambda: PaymentCreate(
            order_id="order-1",
            user_id="user-1",
            amount_minor=0,
            currency="UAH",
            provider="demo",
            idempotency_key="idempotency-1",
        ),
        lambda: PaymentRead(
            **{
                **build_payment(status="unsupported"),
                "amount_minor": 100,
            }
        ),
        lambda: PaymentCreate(
            order_id="order-1",
            user_id="user-1",
            amount_minor=100,
            currency="UAH",
            provider="demo",
            idempotency_key="idempotency-1",
            metadata={"client_secret": "unsafe"},
        ),
        lambda: RefundCreate(
            payment_id="payment-1",
            order_id="order-1",
            amount_minor=0,
            currency="uah",
            provider="demo",
            reason="invalid",
        ),
    ],
)
def test_payment_domain_schemas_reject_invalid_values(schema_factory) -> None:
    with pytest.raises(ValidationError):
        schema_factory()
