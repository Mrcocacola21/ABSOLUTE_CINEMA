"""Provider-neutral payment domain service."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.commands.order_finalization import OrderFinalizationCommand
from app.commands.reservation_expiry import (
    expire_active_payments_for_order,
    sync_expired_reservations_for_session,
)
from app.core.constants import (
    OrderStatuses,
    PAYMENT_STATUS_VALUES,
    PaymentAttemptStatuses,
    PaymentStatuses,
    PaymentWebhookProcessingStatuses,
    REFUND_STATUS_VALUES,
    RefundStatuses,
    Roles,
    TicketStatuses,
)
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ConflictException,
    DatabaseException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.db.transactions import run_transaction_with_retry
from app.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderPaymentCancelRequest,
    ProviderPaymentCreateRequest,
    ProviderPaymentCreateResult,
    ProviderPaymentStatusRequest,
    ProviderPaymentStatusResult,
    ProviderRefundResult,
)
from app.repositories.orders import OrderRepository
from app.repositories.movies import MovieRepository
from app.repositories.payment_audit_events import PaymentAuditEventRepository
from app.repositories.payment_attempts import PaymentAttemptRepository
from app.repositories.payment_webhook_events import PaymentWebhookEventRepository
from app.repositories.payments import PaymentRepository
from app.repositories.refunds import RefundRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.schemas.payment import (
    AdminPaymentCustomerRead,
    AdminPaymentDetailsRead,
    AdminPaymentListItemRead,
    AdminPaymentOrderContextRead,
    DEFAULT_PAYMENT_CURRENCY,
    PaymentDetailsRead,
    PaymentAttemptCreate,
    PaymentAttemptRead,
    PaymentAuditEventCreate,
    PaymentCreate,
    PaymentInitiationRead,
    PaymentReportMovieAggregateRead,
    PaymentReportPeriodRead,
    PaymentReportRead,
    PaymentReportSessionAggregateRead,
    PaymentReportSummaryRead,
    PaymentRead,
    PaymentWebhookEventCreate,
    PaymentWebhookEventRead,
    PaymentWebhookProcessingRead,
    RefundRead,
    SAFE_SENSITIVE_KEY_MARKERS,
    normalize_provider,
    validate_safe_snapshot,
)
from app.schemas.user import UserRead
from app.services.refund import RefundService
from app.utils.money import amount_to_minor_units

logger = get_logger(__name__)

PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatuses.CREATED: {
        PaymentStatuses.PENDING,
        PaymentStatuses.REQUIRES_ACTION,
        PaymentStatuses.SUCCEEDED,
        PaymentStatuses.FAILED,
        PaymentStatuses.CANCELLED,
        PaymentStatuses.EXPIRED,
    },
    PaymentStatuses.PENDING: {
        PaymentStatuses.REQUIRES_ACTION,
        PaymentStatuses.SUCCEEDED,
        PaymentStatuses.FAILED,
        PaymentStatuses.CANCELLED,
        PaymentStatuses.EXPIRED,
    },
    PaymentStatuses.REQUIRES_ACTION: {
        PaymentStatuses.PENDING,
        PaymentStatuses.SUCCEEDED,
        PaymentStatuses.FAILED,
        PaymentStatuses.CANCELLED,
        PaymentStatuses.EXPIRED,
    },
    PaymentStatuses.SUCCEEDED: {
        PaymentStatuses.PARTIALLY_REFUNDED,
        PaymentStatuses.REFUNDED,
    },
    PaymentStatuses.PARTIALLY_REFUNDED: {
        PaymentStatuses.REFUNDED,
    },
}

ATTEMPT_TRANSITIONS: dict[str, set[str]] = {
    PaymentAttemptStatuses.CREATED: {
        PaymentAttemptStatuses.PENDING,
        PaymentAttemptStatuses.SUCCEEDED,
        PaymentAttemptStatuses.FAILED,
    },
    PaymentAttemptStatuses.PENDING: {
        PaymentAttemptStatuses.SUCCEEDED,
        PaymentAttemptStatuses.FAILED,
    },
}

REUSABLE_PAYMENT_STATUSES = {
    PaymentStatuses.CREATED,
    PaymentStatuses.PENDING,
    PaymentStatuses.REQUIRES_ACTION,
}
BLOCKING_PAYMENT_STATUSES = {
    PaymentStatuses.CREATED,
    PaymentStatuses.PENDING,
    PaymentStatuses.REQUIRES_ACTION,
    PaymentStatuses.SUCCEEDED,
}
TERMINAL_PAYMENT_STATUSES = {
    PaymentStatuses.SUCCEEDED,
    PaymentStatuses.FAILED,
    PaymentStatuses.CANCELLED,
    PaymentStatuses.EXPIRED,
    PaymentStatuses.REFUNDED,
    PaymentStatuses.PARTIALLY_REFUNDED,
}
RETRYABLE_PAYMENT_STATUSES = {
    PaymentStatuses.FAILED,
    PaymentStatuses.CANCELLED,
    PaymentStatuses.EXPIRED,
}
ADMIN_REFUND_RESERVED_STATUSES = {
    RefundStatuses.CREATED,
    RefundStatuses.PENDING,
    RefundStatuses.SUCCEEDED,
}
ADMIN_REFUNDABLE_PAYMENT_STATUSES = {
    PaymentStatuses.SUCCEEDED,
    PaymentStatuses.PARTIALLY_REFUNDED,
}
FINANCIAL_SUCCESS_PAYMENT_STATUSES = {
    PaymentStatuses.SUCCEEDED,
    PaymentStatuses.PARTIALLY_REFUNDED,
    PaymentStatuses.REFUNDED,
}
REPORT_PENDING_PAYMENT_STATUSES = {
    PaymentStatuses.CREATED,
    PaymentStatuses.PENDING,
    PaymentStatuses.REQUIRES_ACTION,
}


class PaymentService:
    """Service for provider-neutral payment aggregate operations."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        payment_attempt_repository: PaymentAttemptRepository,
        payment_webhook_event_repository: PaymentWebhookEventRepository,
        refund_repository: RefundRepository,
        order_repository: OrderRepository,
        ticket_repository: TicketRepository,
        session_repository: SessionRepository,
        payment_provider: PaymentProvider,
        payment_audit_event_repository: PaymentAuditEventRepository | None = None,
        user_repository: UserRepository | None = None,
        movie_repository: MovieRepository | None = None,
    ) -> None:
        self.payment_repository = payment_repository
        self.payment_attempt_repository = payment_attempt_repository
        self.payment_webhook_event_repository = payment_webhook_event_repository
        self.payment_audit_event_repository = payment_audit_event_repository
        self.refund_repository = refund_repository
        self.order_repository = order_repository
        self.ticket_repository = ticket_repository
        self.session_repository = session_repository
        self.user_repository = user_repository
        self.movie_repository = movie_repository
        self.payment_provider = payment_provider
        self.refund_service = RefundService(
            refund_repository=refund_repository,
            payment_repository=payment_repository,
            payment_provider=payment_provider,
            payment_audit_event_repository=payment_audit_event_repository,
        )
        self.order_finalization_command = OrderFinalizationCommand(
            order_repository=order_repository,
            ticket_repository=ticket_repository,
            session_repository=session_repository,
        )

    async def initiate_order_payment(
        self,
        *,
        order_id: str,
        current_user: UserRead,
        idempotency_key: str | None = None,
        currency: str = DEFAULT_PAYMENT_CURRENCY,
        metadata: dict[str, Any] | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> PaymentInitiationRead:
        """Create or reuse an order payment and initiate provider checkout."""
        now = datetime.now(tz=timezone.utc)
        order_document = await self._get_payable_order(
            order_id,
            current_user=current_user,
            now=now,
        )
        return await self._initiate_payment_for_order_document(
            order_document=order_document,
            provider=None,
            idempotency_key=idempotency_key,
            currency=currency,
            metadata=metadata,
            return_url=return_url,
            cancel_url=cancel_url,
            now=now,
        )

    async def retry_order_payment(
        self,
        *,
        order_id: str,
        current_user: UserRead,
        idempotency_key: str | None = None,
        currency: str = DEFAULT_PAYMENT_CURRENCY,
        metadata: dict[str, Any] | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> PaymentInitiationRead:
        """Start a new payment after a previous non-success payment while the reservation is still active."""
        now = datetime.now(tz=timezone.utc)
        order_document = await self._get_payable_order(
            order_id,
            current_user=current_user,
            now=now,
        )
        order_payments = await self.payment_repository.list_by_order(order_id)
        self._ensure_retry_is_allowed(order_payments)

        normalized_idempotency_key = self._normalize_idempotency_key(idempotency_key)
        if normalized_idempotency_key is not None:
            existing_by_key = await self.payment_repository.get_by_idempotency_key(normalized_idempotency_key)
            if existing_by_key is not None:
                raise ConflictException("Payment retry idempotency key is already used.")

        return await self._initiate_payment_for_order_document(
            order_document=order_document,
            provider=None,
            idempotency_key=normalized_idempotency_key,
            currency=currency,
            metadata=metadata,
            return_url=return_url,
            cancel_url=cancel_url,
            now=now,
        )

    async def get_payment_details(
        self,
        payment_id: str,
        *,
        current_user: UserRead,
    ) -> PaymentDetailsRead:
        """Return a payment and safe attempt history if the user may inspect it."""
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_access(payment, current_user=current_user)
        payment = await self._sync_payment_order_expiry_if_elapsed(payment, now=datetime.now(tz=timezone.utc))
        return await self._build_payment_details(payment)

    async def get_order_payment_details(
        self,
        order_id: str,
        *,
        current_user: UserRead,
    ) -> PaymentDetailsRead:
        """Return the latest payment for an accessible order."""
        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        self._ensure_order_access(order_document, current_user=current_user)
        order_document = await self._sync_order_expiry_if_elapsed(order_document, now=datetime.now(tz=timezone.utc))

        payments = await self.payment_repository.list_by_order(order_id)
        if not payments:
            raise NotFoundException("Payment for this order was not found.")
        latest_payment = PaymentRead.model_validate(payments[0])
        return await self._build_payment_details(latest_payment)

    async def process_provider_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str] | None = None,
    ) -> PaymentWebhookProcessingRead:
        """Verify, persist, deduplicate, and process a provider webhook."""
        now = datetime.now(tz=timezone.utc)
        provider_name = normalize_provider(self.payment_provider.name)
        payload_hash = self._hash_webhook_payload(raw_body)
        payload_snapshot = self._safe_webhook_payload_snapshot(raw_body)

        try:
            await self.payment_provider.verify_webhook_signature(
                raw_body=raw_body,
                headers=headers,
            )
        except PaymentProviderError as exc:
            await self._store_unverified_webhook_event(
                provider=provider_name,
                payload_hash=payload_hash,
                payload_snapshot=payload_snapshot,
                error_message=exc.message,
                now=now,
            )
            logger.warning(
                "Rejected payment webhook with invalid signature",
                extra={"provider": provider_name, "error_code": exc.code},
            )
            raise AuthenticationException("Invalid payment webhook signature.") from exc

        try:
            provider_event = await self.payment_provider.parse_webhook(
                raw_body=raw_body,
                headers=headers,
            )
        except PaymentProviderError as exc:
            await self._store_verified_failed_webhook_event(
                provider=provider_name,
                payload_hash=payload_hash,
                payload_snapshot=payload_snapshot,
                error_message=exc.message,
                now=now,
            )
            raise ValidationException("Malformed payment webhook payload.") from exc

        if normalize_provider(provider_event.provider) != provider_name:
            raise ConflictException("Webhook provider does not match the configured payment provider.")

        provider_event_id = provider_event.event_id or f"payload-{payload_hash}"
        event_record, duplicate_done = await self._get_or_create_webhook_event(
            provider=provider_name,
            provider_event_id=provider_event_id,
            event_type=provider_event.event_type,
            payload_hash=payload_hash,
            payload_snapshot=payload_snapshot,
            now=now,
        )
        if duplicate_done:
            return PaymentWebhookProcessingRead(
                event_id=event_record.id,
                provider=event_record.provider,
                provider_event_id=event_record.provider_event_id,
                event_type=event_record.event_type,
                processing_status=event_record.processing_status,
                duplicate=True,
                message="Payment webhook event was already processed.",
            )

        try:
            return await run_transaction_with_retry(
                lambda db_session: self._process_webhook_event_transaction(
                    event_record=event_record,
                    provider_event=provider_event,
                    now=now,
                    db_session=db_session,
                ),
                operation_name="process_payment_webhook",
            )
        except Exception as exc:
            await self.payment_webhook_event_repository.update_processing_status(
                event_record.id,
                processing_status=PaymentWebhookProcessingStatuses.FAILED,
                updated_at=datetime.now(tz=timezone.utc),
                error_message=str(exc)[:1000],
            )
            logger.exception(
                "Payment webhook processing failed",
                extra={
                    "provider": provider_name,
                    "provider_event_id": provider_event_id,
                    "event_type": provider_event.event_type,
                },
                exc_info=exc,
            )
            raise

    async def create_payment_for_order(
        self,
        *,
        order_id: str,
        provider: str | None = None,
        idempotency_key: str,
        currency: str = DEFAULT_PAYMENT_CURRENCY,
        metadata: dict[str, Any] | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> PaymentRead:
        """Create or reuse an order payment and initiate it through the configured provider."""
        now = datetime.now(tz=timezone.utc)
        order_document = await self._get_payable_order(order_id, current_user=None, now=now)
        initiation = await self._initiate_payment_for_order_document(
            order_document=order_document,
            provider=provider,
            idempotency_key=idempotency_key,
            currency=currency,
            metadata=metadata,
            return_url=return_url,
            cancel_url=cancel_url,
            now=now,
        )
        return await self._get_payment_or_not_found(initiation.payment_id)

    async def _initiate_payment_for_order_document(
        self,
        *,
        order_document: dict[str, Any],
        provider: str | None,
        idempotency_key: str | None,
        currency: str,
        metadata: dict[str, Any] | None,
        return_url: str | None,
        cancel_url: str | None,
        now: datetime,
    ) -> PaymentInitiationRead:
        provider_name = self._resolve_provider_name(provider)
        normalized_idempotency_key = self._normalize_idempotency_key(idempotency_key)
        order_id = str(order_document["id"])

        if normalized_idempotency_key is not None:
            existing_by_key = await self.payment_repository.get_by_idempotency_key(normalized_idempotency_key)
            if existing_by_key is not None:
                payment = PaymentRead.model_validate(existing_by_key)
                self._ensure_idempotent_payment_matches_order(
                    payment=payment,
                    order_document=order_document,
                    provider_name=provider_name,
                )
                return await self._build_initiation_response_from_payment(
                    payment=payment,
                    order_document=order_document,
                    reused=True,
                )

        order_payments = await self.payment_repository.list_by_order(order_id)
        self._ensure_order_has_no_completed_payment(order_payments)

        reusable_payment_document = self._find_reusable_payment(order_payments, provider_name=provider_name)
        if reusable_payment_document is not None:
            payment = PaymentRead.model_validate(reusable_payment_document)
            if self._has_provider_initiation(payment):
                return await self._build_initiation_response_from_payment(
                    payment=payment,
                    order_document=order_document,
                    reused=True,
                )
            return await self._initiate_provider_payment(
                payment=payment,
                order_document=order_document,
                metadata=metadata,
                return_url=return_url,
                cancel_url=cancel_url,
                reused_payment=True,
            )

        payment_idempotency_key = normalized_idempotency_key or self._generate_payment_idempotency_key(
            order_id=order_id,
            provider_name=provider_name,
        )
        try:
            payment = await self._create_payment_record(
                order_document=order_document,
                provider_name=provider_name,
                idempotency_key=payment_idempotency_key,
                currency=currency,
                metadata=metadata,
                now=now,
            )
        except ConflictException:
            concurrent_payments = await self.payment_repository.list_by_order(order_id)
            reusable_payment_document = self._find_reusable_payment(
                concurrent_payments,
                provider_name=provider_name,
            )
            if reusable_payment_document is None:
                raise
            return await self._build_initiation_response_from_payment(
                payment=PaymentRead.model_validate(reusable_payment_document),
                order_document=order_document,
                reused=True,
            )

        return await self._initiate_provider_payment(
            payment=payment,
            order_document=order_document,
            metadata=metadata,
            return_url=return_url,
            cancel_url=cancel_url,
            reused_payment=False,
        )

    async def _create_payment_record(
        self,
        *,
        order_document: dict[str, Any],
        provider_name: str,
        idempotency_key: str,
        currency: str,
        metadata: dict[str, Any] | None,
        now: datetime,
    ) -> PaymentRead:
        payment_payload = PaymentCreate(
            order_id=str(order_document["id"]),
            user_id=str(order_document["user_id"]),
            amount_minor=amount_to_minor_units(order_document["total_price"]),
            currency=currency,
            provider=provider_name,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
        created = await self.payment_repository.create_payment(
            {
                **payment_payload.model_dump(mode="python"),
                "status": PaymentStatuses.CREATED,
                "provider_payment_id": None,
                "failure_code": None,
                "failure_message": None,
                "created_at": now,
                "updated_at": None,
            }
        )
        return PaymentRead.model_validate(created)

    async def _initiate_provider_payment(
        self,
        *,
        payment: PaymentRead,
        order_document: dict[str, Any],
        metadata: dict[str, Any] | None,
        return_url: str | None,
        cancel_url: str | None,
        reused_payment: bool,
    ) -> PaymentInitiationRead:
        attempt = await self.create_payment_attempt(
            payment_id=payment.id,
            request_payload_snapshot={
                "operation": "create_payment",
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "external_order_reference": self._build_external_order_reference(order_document),
                "amount_minor": payment.amount_minor,
                "currency": payment.currency,
                "description": self._build_payment_description(order_document),
                "has_return_url": return_url is not None,
                "has_cancel_url": cancel_url is not None,
                "metadata_keys": sorted((metadata or {}).keys()),
            },
        )
        await self.mark_attempt_pending(attempt.id)

        logger.info(
            "Initiating payment provider checkout",
            extra={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "provider": payment.provider,
                "attempt_id": attempt.id,
            },
        )
        try:
            provider_result = await self.payment_provider.create_payment(
                ProviderPaymentCreateRequest(
                    payment_id=payment.id,
                    order_id=payment.order_id,
                    external_order_reference=self._build_external_order_reference(order_document),
                    user_id=payment.user_id,
                    amount_minor=payment.amount_minor,
                    currency=payment.currency,
                    idempotency_key=payment.idempotency_key,
                    description=self._build_payment_description(order_document),
                    metadata=self._build_provider_metadata(
                        payment=payment,
                        order_document=order_document,
                        client_metadata=metadata,
                    ),
                    return_url=return_url,
                    cancel_url=cancel_url,
                )
            )
        except PaymentProviderError as exc:
            await self.mark_attempt_failed(
                attempt.id,
                error_code=exc.code,
                error_message=exc.message,
                response_payload_snapshot=self._provider_error_snapshot(exc),
            )
            await self.mark_payment_failed(
                payment.id,
                failure_code=exc.code,
                failure_message=exc.message,
            )
            logger.info(
                "Payment provider checkout initiation failed",
                extra={
                    "payment_id": payment.id,
                    "order_id": payment.order_id,
                    "provider": payment.provider,
                    "attempt_id": attempt.id,
                    "error_code": exc.code,
                },
            )
            raise ConflictException("Payment provider failed to create payment.") from exc

        updated_attempt = await self._mark_attempt_from_provider_create_result(attempt.id, provider_result)
        updated_payment = await self._apply_payment_provider_result(payment.id, provider_result)
        await self._record_audit_event(
            action="payment.initiated",
            actor_type="user",
            actor_id=updated_payment.user_id,
            payment_id=updated_payment.id,
            order_id=updated_payment.order_id,
            provider=updated_payment.provider,
            old_status=payment.status,
            new_status=updated_payment.status,
            safe_context={
                "attempt_id": updated_attempt.id,
                "reused_payment": reused_payment,
                "has_redirect_url": provider_result.redirect_url is not None,
            },
        )
        logger.info(
            "Payment provider checkout initiated",
            extra={
                "payment_id": updated_payment.id,
                "order_id": updated_payment.order_id,
                "provider": updated_payment.provider,
                "attempt_id": updated_attempt.id,
                "payment_status": updated_payment.status,
                "attempt_status": updated_attempt.status,
            },
        )
        return self._build_initiation_response(
            payment=updated_payment,
            order_document=order_document,
            attempt=updated_attempt,
            provider_result=provider_result,
            reused=reused_payment,
        )

    async def create_payment_attempt(
        self,
        *,
        payment_id: str,
        provider_attempt_id: str | None = None,
        request_payload_snapshot: dict[str, Any] | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
    ) -> PaymentAttemptRead:
        """Create a provider-neutral attempt record for a payment."""
        payment = await self._get_payment_or_not_found(payment_id)
        now = datetime.now(tz=timezone.utc)
        attempt_payload = PaymentAttemptCreate(
            payment_id=payment.id,
            order_id=payment.order_id,
            provider=payment.provider,
            provider_attempt_id=provider_attempt_id,
            request_payload_snapshot=request_payload_snapshot,
            response_payload_snapshot=response_payload_snapshot,
        )
        created = await self.payment_attempt_repository.create_attempt(
            {
                **attempt_payload.model_dump(mode="python"),
                "status": PaymentAttemptStatuses.CREATED,
                "error_code": None,
                "error_message": None,
                "created_at": now,
                "updated_at": None,
            }
        )
        return PaymentAttemptRead.model_validate(created)

    async def refresh_payment_status(self, payment_id: str) -> PaymentRead:
        """Fetch and persist the provider-normalized payment status."""
        payment = await self._get_payment_or_not_found(payment_id)
        provider_payment_id = self._require_provider_payment_id(payment)

        try:
            provider_result = await self.payment_provider.get_payment_status(
                ProviderPaymentStatusRequest(
                    payment_id=payment.id,
                    provider_payment_id=provider_payment_id,
                    expected_amount_minor=payment.amount_minor,
                    expected_currency=payment.currency,
                )
            )
        except PaymentProviderError as exc:
            raise ConflictException(f"Payment provider status lookup failed: {exc.message}") from exc

        return await self._apply_payment_provider_result(payment.id, provider_result)

    async def cancel_payment(
        self,
        payment_id: str,
        *,
        reason: str | None = None,
    ) -> PaymentRead:
        """Cancel a payment through the configured provider and persist the result."""
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_transition(payment.status, PaymentStatuses.CANCELLED)
        provider_payment_id = self._require_provider_payment_id(payment)

        try:
            provider_result = await self.payment_provider.cancel_payment(
                ProviderPaymentCancelRequest(
                    payment_id=payment.id,
                    provider_payment_id=provider_payment_id,
                    expected_amount_minor=payment.amount_minor,
                    expected_currency=payment.currency,
                    reason=reason,
                )
            )
        except PaymentProviderError as exc:
            raise ConflictException(f"Payment provider cancellation failed: {exc.message}") from exc

        return await self._apply_payment_provider_result(payment.id, provider_result)

    async def refund_payment(
        self,
        *,
        payment_id: str,
        amount_minor: int | None,
        reason: str,
        requested_by: str = "system",
        metadata: dict[str, Any] | None = None,
        fail_on_provider_error: bool = True,
    ) -> RefundRead:
        """Create a provider-backed full or partial refund and persist the normalized result."""
        return await self.refund_service.refund_payment(
            payment_id=payment_id,
            amount_minor=amount_minor,
            reason=reason,
            requested_by=requested_by,
            metadata=metadata,
            fail_on_provider_error=fail_on_provider_error,
        )

    async def list_payment_refunds(
        self,
        payment_id: str,
        *,
        current_user: UserRead,
    ) -> list[RefundRead]:
        """Return refunds for an accessible payment."""
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_access(payment, current_user=current_user)
        return await self.refund_service.list_payment_refunds(payment_id)

    async def list_order_refunds(
        self,
        order_id: str,
        *,
        current_user: UserRead,
    ) -> list[RefundRead]:
        """Return refunds for an accessible order."""
        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        self._ensure_order_access(order_document, current_user=current_user)
        return await self.refund_service.list_order_refunds(order_id)

    async def list_admin_payments(
        self,
        *,
        status: str | None = None,
        provider: str | None = None,
        refund_status: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminPaymentListItemRead]:
        """Return enriched payments for the protected admin workspace."""
        if status is not None and status not in PAYMENT_STATUS_VALUES:
            raise ValidationException("Unsupported payment status filter.")
        if refund_status is not None and refund_status not in {*REFUND_STATUS_VALUES, "all", "none"}:
            raise ValidationException("Unsupported refund status filter.")
        normalized_provider = normalize_provider(provider) if provider else None
        normalized_search = search.strip().lower() if search else ""
        search_limit = max(limit + offset, 200) if normalized_search else limit
        search_offset = 0 if normalized_search else offset
        payment_documents = await self.payment_repository.list_admin_payments(
            status=status,
            provider=normalized_provider,
            search=None,
            limit=search_limit,
            offset=search_offset,
        )

        items: list[AdminPaymentListItemRead] = []
        for payment_document in payment_documents:
            payment = PaymentRead.model_validate(payment_document)
            item = await self._build_admin_payment_list_item(payment)
            if refund_status and refund_status != "all":
                if refund_status == "none":
                    if item.refunds_count != 0:
                        continue
                elif item.latest_refund_status != refund_status:
                    continue
            if normalized_search and not self._admin_payment_matches_search(item, normalized_search):
                continue
            items.append(item)

        if normalized_search:
            return items[offset : offset + limit]
        return items

    async def get_admin_payment_details(self, payment_id: str) -> AdminPaymentDetailsRead:
        """Return one payment with attempts, refunds, webhook rows, and booking context for admins."""
        payment_document = await self.payment_repository.get_by_id(payment_id)
        if payment_document is None:
            raise NotFoundException("Payment was not found.")
        payment = PaymentRead.model_validate(payment_document)
        attempts = [
            PaymentAttemptRead.model_validate(attempt)
            for attempt in await self.payment_attempt_repository.list_by_payment(payment.id)
        ]
        refunds = [
            RefundRead.model_validate(refund)
            for refund in await self.refund_repository.list_by_payment(payment.id)
        ]
        provider_refund_ids = [
            refund.provider_refund_id
            for refund in refunds
            if refund.provider_refund_id is not None
        ]
        webhook_events = [
            PaymentWebhookEventRead.model_validate(event)
            for event in await self.payment_webhook_event_repository.list_by_payment_context(
                payment_id=payment.id,
                order_id=payment.order_id,
                provider=payment.provider,
                provider_payment_id=payment.provider_payment_id,
                provider_refund_ids=provider_refund_ids,
            )
        ]
        order = await self._build_admin_order_context(payment.order_id)
        customer = await self._build_admin_customer(payment.user_id)
        aggregate = self._build_admin_refund_aggregate(payment, refunds)

        return AdminPaymentDetailsRead(
            **payment.model_dump(mode="python"),
            attempts=attempts,
            refunds=refunds,
            webhook_events=webhook_events,
            order=order,
            customer=customer,
            attempts_count=len(attempts),
            refunds_count=len(refunds),
            **aggregate,
        )

    async def get_admin_payment_report(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> PaymentReportRead:
        """Build admin payment revenue metrics for the selected financial period."""
        normalized_date_from = self._normalize_report_datetime(date_from)
        normalized_date_to = self._normalize_report_datetime(date_to)
        if (
            normalized_date_from is not None
            and normalized_date_to is not None
            and normalized_date_from > normalized_date_to
        ):
            raise ValidationException("date_from must be before or equal to date_to.")

        payment_documents = await self.payment_repository.list_admin_payments_for_report(
            date_from=normalized_date_from,
            date_to=normalized_date_to,
        )
        refund_documents = await self.refund_repository.list_admin_refunds_for_report(
            date_from=normalized_date_from,
            date_to=normalized_date_to,
        )
        period_payments = [PaymentRead.model_validate(document) for document in payment_documents]
        period_refunds = [RefundRead.model_validate(document) for document in refund_documents]
        succeeded_period_refunds = [
            refund
            for refund in period_refunds
            if refund.status == RefundStatuses.SUCCEEDED
        ]
        currency = self._resolve_report_currency(period_payments, succeeded_period_refunds)

        report_payments_by_id = {payment.id: payment for payment in period_payments}
        for refund in succeeded_period_refunds:
            if refund.payment_id in report_payments_by_id:
                continue
            refund_payment_document = await self.payment_repository.get_by_id(refund.payment_id)
            if refund_payment_document is not None:
                report_payments_by_id[refund.payment_id] = PaymentRead.model_validate(refund_payment_document)

        order_documents = await self._load_report_orders(
            [payment.order_id for payment in report_payments_by_id.values()]
        )
        session_documents = await self._load_report_sessions(
            [
                str(order["session_id"])
                for order in order_documents.values()
                if order.get("session_id") is not None
            ]
        )
        movie_documents = await self._load_report_movies(
            [
                str(session["movie_id"])
                for session in session_documents.values()
                if session.get("movie_id") is not None
            ]
        )

        total_payments_count = len(period_payments)
        succeeded_payments = [
            payment
            for payment in period_payments
            if payment.status in FINANCIAL_SUCCESS_PAYMENT_STATUSES
        ]
        gross_revenue_minor = sum(payment.amount_minor for payment in succeeded_payments)
        refunded_amount_minor = sum(refund.amount_minor for refund in succeeded_period_refunds)
        paid_order_ids: set[str] = set()
        paid_tickets_count = 0
        session_aggregates: dict[str, dict[str, Any]] = {}
        session_order_ids: dict[str, set[str]] = {}
        movie_aggregates: dict[str, dict[str, Any]] = {}
        movie_order_ids: dict[str, set[str]] = {}
        movie_session_ids: dict[str, set[str]] = {}

        for payment in succeeded_payments:
            context = self._build_report_context(
                payment=payment,
                orders=order_documents,
                sessions=session_documents,
                movies=movie_documents,
            )
            if context["order"] is not None and payment.order_id not in paid_order_ids:
                paid_order_ids.add(payment.order_id)
                paid_tickets_count += self._report_order_tickets_count(context["order"])
            self._add_payment_to_report_aggregates(
                payment=payment,
                context=context,
                currency=currency,
                session_aggregates=session_aggregates,
                session_order_ids=session_order_ids,
                movie_aggregates=movie_aggregates,
                movie_order_ids=movie_order_ids,
                movie_session_ids=movie_session_ids,
            )

        for refund in succeeded_period_refunds:
            payment = report_payments_by_id.get(refund.payment_id)
            if payment is None:
                continue
            context = self._build_report_context(
                payment=payment,
                orders=order_documents,
                sessions=session_documents,
                movies=movie_documents,
            )
            self._add_refund_to_report_aggregates(
                refund=refund,
                context=context,
                currency=currency,
                session_aggregates=session_aggregates,
                movie_aggregates=movie_aggregates,
            )

        summary = PaymentReportSummaryRead(
            currency=currency,
            total_payments_count=total_payments_count,
            succeeded_payments_count=len(succeeded_payments),
            failed_payments_count=sum(1 for payment in period_payments if payment.status == PaymentStatuses.FAILED),
            pending_payments_count=sum(
                1
                for payment in period_payments
                if payment.status in REPORT_PENDING_PAYMENT_STATUSES
            ),
            cancelled_payments_count=sum(
                1
                for payment in period_payments
                if payment.status == PaymentStatuses.CANCELLED
            ),
            expired_payments_count=sum(1 for payment in period_payments if payment.status == PaymentStatuses.EXPIRED),
            refunded_payments_count=sum(1 for payment in period_payments if payment.status == PaymentStatuses.REFUNDED),
            partially_refunded_payments_count=sum(
                1
                for payment in period_payments
                if payment.status == PaymentStatuses.PARTIALLY_REFUNDED
            ),
            gross_revenue_minor=gross_revenue_minor,
            refunded_amount_minor=refunded_amount_minor,
            net_revenue_minor=gross_revenue_minor - refunded_amount_minor,
            succeeded_orders_count=len(paid_order_ids),
            paid_tickets_count=paid_tickets_count,
            success_rate=(len(succeeded_payments) / total_payments_count) if total_payments_count else 0,
        )

        sessions = [
            self._build_report_session_read(aggregate, order_ids=session_order_ids.get(session_id, set()))
            for session_id, aggregate in session_aggregates.items()
        ]
        movies = [
            self._build_report_movie_read(
                aggregate,
                order_ids=movie_order_ids.get(movie_id, set()),
                session_ids=movie_session_ids.get(movie_id, set()),
            )
            for movie_id, aggregate in movie_aggregates.items()
        ]

        sessions.sort(key=lambda item: (item.net_revenue_minor, item.gross_revenue_minor), reverse=True)
        movies.sort(key=lambda item: (item.net_revenue_minor, item.gross_revenue_minor), reverse=True)

        return PaymentReportRead(
            generated_at=datetime.now(tz=timezone.utc),
            period=PaymentReportPeriodRead(date_from=normalized_date_from, date_to=normalized_date_to),
            summary=summary,
            sessions=sessions,
            movies=movies,
        )

    async def mark_payment_pending(
        self,
        payment_id: str,
        *,
        provider_payment_id: str | None = None,
    ) -> PaymentRead:
        """Move a payment into pending state."""
        return await self._mark_payment_status(
            payment_id,
            PaymentStatuses.PENDING,
            provider_payment_id=provider_payment_id,
        )

    async def mark_payment_requires_action(
        self,
        payment_id: str,
        *,
        provider_payment_id: str | None = None,
    ) -> PaymentRead:
        """Move a payment into a customer-action-required state."""
        return await self._mark_payment_status(
            payment_id,
            PaymentStatuses.REQUIRES_ACTION,
            provider_payment_id=provider_payment_id,
        )

    async def mark_payment_succeeded(
        self,
        payment_id: str,
        *,
        provider_payment_id: str | None = None,
    ) -> PaymentRead:
        """Mark a payment as financially successful."""
        return await self._mark_payment_status(
            payment_id,
            PaymentStatuses.SUCCEEDED,
            provider_payment_id=provider_payment_id,
        )

    async def mark_payment_failed(
        self,
        payment_id: str,
        *,
        provider_payment_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> PaymentRead:
        """Mark a payment as failed with safe failure details."""
        if not (failure_code or failure_message):
            raise ConflictException("Failed payments require a failure code or message.")
        return await self._mark_payment_status(
            payment_id,
            PaymentStatuses.FAILED,
            provider_payment_id=provider_payment_id,
            failure_code=failure_code,
            failure_message=failure_message,
        )

    async def mark_payment_cancelled(
        self,
        payment_id: str,
        *,
        provider_payment_id: str | None = None,
    ) -> PaymentRead:
        """Mark a payment as cancelled."""
        return await self._mark_payment_status(
            payment_id,
            PaymentStatuses.CANCELLED,
            provider_payment_id=provider_payment_id,
        )

    async def mark_payment_expired(
        self,
        payment_id: str,
        *,
        provider_payment_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> PaymentRead:
        """Mark a payment as expired because checkout or the reservation timed out."""
        return await self._mark_payment_status(
            payment_id,
            PaymentStatuses.EXPIRED,
            provider_payment_id=provider_payment_id,
            failure_code=failure_code,
            failure_message=failure_message,
        )

    async def mark_attempt_pending(self, attempt_id: str) -> PaymentAttemptRead:
        """Move a payment attempt into pending state."""
        return await self._mark_attempt_status(attempt_id, PaymentAttemptStatuses.PENDING)

    async def mark_attempt_succeeded(
        self,
        attempt_id: str,
        *,
        provider_attempt_id: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
    ) -> PaymentAttemptRead:
        """Mark a payment attempt as succeeded."""
        if response_payload_snapshot is not None:
            response_payload_snapshot = validate_safe_snapshot(
                response_payload_snapshot,
                field_name="response_payload_snapshot",
            )
        return await self._mark_attempt_status(
            attempt_id,
            PaymentAttemptStatuses.SUCCEEDED,
            provider_attempt_id=provider_attempt_id,
            response_payload_snapshot=response_payload_snapshot,
        )

    async def mark_attempt_failed(
        self,
        attempt_id: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
    ) -> PaymentAttemptRead:
        """Mark a payment attempt as failed."""
        if response_payload_snapshot is not None:
            response_payload_snapshot = validate_safe_snapshot(
                response_payload_snapshot,
                field_name="response_payload_snapshot",
            )
        return await self._mark_attempt_status(
            attempt_id,
            PaymentAttemptStatuses.FAILED,
            response_payload_snapshot=response_payload_snapshot,
            error_code=error_code,
            error_message=error_message,
        )

    async def _mark_attempt_from_provider_create_result(
        self,
        attempt_id: str,
        provider_result: ProviderPaymentCreateResult,
    ) -> PaymentAttemptRead:
        snapshot = self._provider_result_snapshot(provider_result)
        if provider_result.status == PaymentStatuses.FAILED:
            return await self.mark_attempt_failed(
                attempt_id,
                error_code=provider_result.failure_code or "provider_payment_failed",
                error_message=provider_result.failure_message,
                response_payload_snapshot=snapshot,
            )

        return await self.mark_attempt_succeeded(
            attempt_id,
            provider_attempt_id=provider_result.provider_attempt_id,
            response_payload_snapshot=snapshot,
        )

    async def _apply_payment_provider_result(
        self,
        payment_id: str,
        provider_result: ProviderPaymentCreateResult | ProviderPaymentStatusResult,
    ) -> PaymentRead:
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_provider_result_matches(payment, provider_result)

        if provider_result.status == PaymentStatuses.CREATED:
            return await self._mark_payment_status(
                payment.id,
                PaymentStatuses.CREATED,
                provider_payment_id=provider_result.provider_payment_id,
            )
        if provider_result.status == PaymentStatuses.PENDING:
            return await self.mark_payment_pending(
                payment.id,
                provider_payment_id=provider_result.provider_payment_id,
            )
        if provider_result.status == PaymentStatuses.REQUIRES_ACTION:
            return await self.mark_payment_requires_action(
                payment.id,
                provider_payment_id=provider_result.provider_payment_id,
            )
        if provider_result.status == PaymentStatuses.SUCCEEDED:
            return await self.mark_payment_succeeded(
                payment.id,
                provider_payment_id=provider_result.provider_payment_id,
            )
        if provider_result.status == PaymentStatuses.FAILED:
            return await self.mark_payment_failed(
                payment.id,
                provider_payment_id=provider_result.provider_payment_id,
                failure_code=provider_result.failure_code or "provider_payment_failed",
                failure_message=provider_result.failure_message or "Payment provider reported failure.",
            )
        if provider_result.status == PaymentStatuses.CANCELLED:
            return await self.mark_payment_cancelled(
                payment.id,
                provider_payment_id=provider_result.provider_payment_id,
            )
        if provider_result.status == PaymentStatuses.EXPIRED:
            return await self.mark_payment_expired(
                payment.id,
                provider_payment_id=provider_result.provider_payment_id,
                failure_code=provider_result.failure_code or "provider_payment_expired",
                failure_message=provider_result.failure_message or "Payment provider reported checkout expiration.",
            )
        if provider_result.status in {PaymentStatuses.PARTIALLY_REFUNDED, PaymentStatuses.REFUNDED}:
            return await self._mark_payment_status(
                payment.id,
                provider_result.status,
                provider_payment_id=provider_result.provider_payment_id,
            )

        raise ConflictException(f"Unsupported provider-normalized payment status '{provider_result.status}'.")

    async def _apply_refund_provider_result(
        self,
        refund_id: str,
        provider_result: ProviderRefundResult,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        return await self.refund_service.apply_provider_result(
            refund_id,
            provider_result,
            db_session=db_session,
        )

    def _resolve_provider_name(self, provider: str | None) -> str:
        configured_provider = normalize_provider(self.payment_provider.name)
        if provider is None:
            return configured_provider

        requested_provider = normalize_provider(provider)
        if requested_provider != configured_provider:
            raise ConflictException("Requested payment provider does not match the configured provider.")
        return configured_provider

    def _require_provider_payment_id(self, payment: PaymentRead) -> str:
        if not payment.provider_payment_id:
            raise ConflictException("Payment has not been created with a provider yet.")
        return payment.provider_payment_id

    def _ensure_payment_provider_result_matches(
        self,
        payment: PaymentRead,
        provider_result: ProviderPaymentCreateResult | ProviderPaymentStatusResult,
    ) -> None:
        if normalize_provider(provider_result.provider) != payment.provider:
            raise ConflictException("Payment provider result does not match the local payment provider.")
        if normalize_provider(provider_result.provider) != normalize_provider(self.payment_provider.name):
            raise ConflictException("Payment provider result does not match the configured provider.")
        if provider_result.provider_payment_id != payment.provider_payment_id and payment.provider_payment_id is not None:
            raise ConflictException("Payment provider reference does not match the local payment.")
        if provider_result.amount_minor != payment.amount_minor:
            raise ConflictException("Payment provider amount does not match the local payment.")
        if provider_result.currency != payment.currency:
            raise ConflictException("Payment provider currency does not match the local payment.")

    def _provider_result_snapshot(
        self,
        provider_result: ProviderPaymentCreateResult | ProviderPaymentStatusResult,
    ) -> dict[str, Any]:
        return validate_safe_snapshot(
            provider_result.model_dump(mode="python", exclude_none=True),
            field_name="response_payload_snapshot",
        ) or {}

    def _provider_error_snapshot(self, exc: PaymentProviderError) -> dict[str, Any]:
        return validate_safe_snapshot(
            {
                "error_code": exc.code,
                "error_message": exc.message,
                "safe_metadata": exc.safe_metadata,
            },
            field_name="response_payload_snapshot",
        ) or {}

    async def _store_unverified_webhook_event(
        self,
        *,
        provider: str,
        payload_hash: str,
        payload_snapshot: dict[str, Any] | None,
        error_message: str,
        now: datetime,
    ) -> None:
        created = await self.payment_webhook_event_repository.create_event(
            {
                **PaymentWebhookEventCreate(
                    provider=provider,
                    provider_event_id=None,
                    event_type="unverified",
                    signature_verified=False,
                    payload_hash=payload_hash,
                    payload_snapshot=payload_snapshot,
                    processing_status=PaymentWebhookProcessingStatuses.FAILED,
                    processed_at=now,
                    error_message=error_message,
                ).model_dump(mode="python"),
                "created_at": now,
                "updated_at": now,
            }
        )
        event = PaymentWebhookEventRead.model_validate(created)
        await self._record_audit_event(
            action="webhook.rejected_invalid_signature",
            actor_type="provider",
            webhook_event_id=event.id,
            provider=provider,
            new_status=PaymentWebhookProcessingStatuses.FAILED,
            reason=error_message,
            safe_context={"payload_hash": payload_hash},
        )

    async def _store_verified_failed_webhook_event(
        self,
        *,
        provider: str,
        payload_hash: str,
        payload_snapshot: dict[str, Any] | None,
        error_message: str,
        now: datetime,
    ) -> None:
        try:
            created = await self.payment_webhook_event_repository.create_event(
                {
                    **PaymentWebhookEventCreate(
                        provider=provider,
                        provider_event_id=f"malformed-{payload_hash}",
                        event_type="malformed",
                        signature_verified=True,
                        payload_hash=payload_hash,
                        payload_snapshot=payload_snapshot,
                        processing_status=PaymentWebhookProcessingStatuses.FAILED,
                        processed_at=now,
                        error_message=error_message,
                    ).model_dump(mode="python"),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            event = PaymentWebhookEventRead.model_validate(created)
            await self._record_audit_event(
                action="webhook.rejected_malformed",
                actor_type="provider",
                webhook_event_id=event.id,
                provider=provider,
                new_status=PaymentWebhookProcessingStatuses.FAILED,
                reason=error_message,
                safe_context={"payload_hash": payload_hash},
            )
        except ConflictException:
            return

    async def _get_or_create_webhook_event(
        self,
        *,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload_hash: str,
        payload_snapshot: dict[str, Any] | None,
        now: datetime,
    ) -> tuple[PaymentWebhookEventRead, bool]:
        existing = await self.payment_webhook_event_repository.get_by_provider_event_id(
            provider=provider,
            provider_event_id=provider_event_id,
        )
        if existing is not None:
            event_record = PaymentWebhookEventRead.model_validate(existing)
            if event_record.payload_hash != payload_hash:
                raise ConflictException("Payment webhook event id was already received with a different payload.")
            if event_record.processing_status in {
                PaymentWebhookProcessingStatuses.PROCESSED,
                PaymentWebhookProcessingStatuses.SKIPPED,
            }:
                return event_record, True
            updated = await self.payment_webhook_event_repository.update_processing_status(
                event_record.id,
                processing_status=PaymentWebhookProcessingStatuses.PROCESSING,
                updated_at=now,
                error_message=None,
            )
            return PaymentWebhookEventRead.model_validate(updated or existing), False

        try:
            created = await self.payment_webhook_event_repository.create_event(
                {
                    **PaymentWebhookEventCreate(
                        provider=provider,
                        provider_event_id=provider_event_id,
                        event_type=event_type,
                        signature_verified=True,
                        payload_hash=payload_hash,
                        payload_snapshot=payload_snapshot,
                        processing_status=PaymentWebhookProcessingStatuses.PROCESSING,
                        processed_at=None,
                        error_message=None,
                    ).model_dump(mode="python"),
                    "created_at": now,
                    "updated_at": None,
                }
            )
            return PaymentWebhookEventRead.model_validate(created), False
        except ConflictException:
            existing = await self.payment_webhook_event_repository.get_by_provider_event_id(
                provider=provider,
                provider_event_id=provider_event_id,
            )
            if existing is None:
                raise
            event_record = PaymentWebhookEventRead.model_validate(existing)
            return event_record, event_record.processing_status in {
                PaymentWebhookProcessingStatuses.PROCESSED,
                PaymentWebhookProcessingStatuses.SKIPPED,
            }

    async def _process_webhook_event_transaction(
        self,
        *,
        event_record: PaymentWebhookEventRead,
        provider_event,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> PaymentWebhookProcessingRead:
        if provider_event.payment is None:
            if provider_event.refund is not None:
                return await self._process_refund_webhook_event(
                    event_record=event_record,
                    refund_result=provider_event.refund,
                    now=now,
                    db_session=db_session,
                )
            updated_event = await self.payment_webhook_event_repository.update_processing_status(
                event_record.id,
                processing_status=PaymentWebhookProcessingStatuses.SKIPPED,
                processed_at=now,
                updated_at=now,
                error_message="Webhook event does not contain payment data.",
                db_session=db_session,
            )
            event = PaymentWebhookEventRead.model_validate(updated_event or event_record)
            await self._record_audit_event(
                action="webhook.skipped",
                actor_type="webhook",
                webhook_event_id=event.id,
                provider=event.provider,
                new_status=event.processing_status,
                reason="missing_payment_data",
                db_session=db_session,
            )
            return PaymentWebhookProcessingRead(
                event_id=event.id,
                provider=event.provider,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                processing_status=event.processing_status,
                duplicate=False,
                message="Webhook event was stored but skipped.",
            )

        payment_result = provider_event.payment
        payment_document = await self.payment_repository.get_by_provider_payment_id(
            provider=payment_result.provider,
            provider_payment_id=payment_result.provider_payment_id,
            db_session=db_session,
        )
        if payment_document is None:
            raise NotFoundException("Payment for this webhook event was not found.")
        payment = PaymentRead.model_validate(payment_document)
        self._ensure_payment_provider_result_matches(payment, payment_result)

        transition_status = self._get_webhook_transition_status(payment.status, payment_result.status)
        if transition_status == PaymentWebhookProcessingStatuses.SKIPPED:
            updated_event = await self.payment_webhook_event_repository.update_processing_status(
                event_record.id,
                processing_status=PaymentWebhookProcessingStatuses.SKIPPED,
                processed_at=now,
                updated_at=now,
                error_message=f"Stale payment transition {payment.status}->{payment_result.status} skipped.",
                payment_id=payment.id,
                order_id=payment.order_id,
                db_session=db_session,
            )
            event = PaymentWebhookEventRead.model_validate(updated_event or event_record)
            await self._record_audit_event(
                action="webhook.skipped",
                actor_type="webhook",
                payment_id=payment.id,
                order_id=payment.order_id,
                webhook_event_id=event.id,
                provider=event.provider,
                old_status=payment.status,
                new_status=payment_result.status,
                reason="stale_payment_transition",
                db_session=db_session,
            )
            return PaymentWebhookProcessingRead(
                event_id=event.id,
                provider=event.provider,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                processing_status=event.processing_status,
                duplicate=False,
                payment_id=payment.id,
                order_id=payment.order_id,
                message="Stale payment webhook event was skipped.",
            )

        updated_payment = await self._apply_payment_webhook_result(
            payment=payment,
            payment_result=payment_result,
            now=now,
            db_session=db_session,
        )
        if updated_payment.status == PaymentStatuses.SUCCEEDED:
            await self._finalize_paid_order_from_webhook(
                updated_payment.order_id,
                now=now,
                db_session=db_session,
            )
        elif updated_payment.status in {PaymentStatuses.FAILED, PaymentStatuses.CANCELLED, PaymentStatuses.EXPIRED}:
            await self._release_pending_order_from_webhook(
                updated_payment.order_id,
                payment_status=updated_payment.status,
                now=now,
                db_session=db_session,
            )

        updated_event = await self.payment_webhook_event_repository.update_processing_status(
            event_record.id,
            processing_status=PaymentWebhookProcessingStatuses.PROCESSED,
            processed_at=now,
            updated_at=now,
            error_message=None,
            payment_id=updated_payment.id,
            order_id=updated_payment.order_id,
            db_session=db_session,
        )
        event = PaymentWebhookEventRead.model_validate(updated_event or event_record)
        await self._record_audit_event(
            action="webhook.processed",
            actor_type="webhook",
            payment_id=updated_payment.id,
            order_id=updated_payment.order_id,
            webhook_event_id=event.id,
            provider=event.provider,
            new_status=updated_payment.status,
            db_session=db_session,
        )
        return PaymentWebhookProcessingRead(
            event_id=event.id,
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processing_status=event.processing_status,
            duplicate=False,
            payment_id=updated_payment.id,
            order_id=updated_payment.order_id,
            message="Payment webhook event processed.",
        )

    async def _process_refund_webhook_event(
        self,
        *,
        event_record: PaymentWebhookEventRead,
        refund_result: ProviderRefundResult,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> PaymentWebhookProcessingRead:
        refund_document = await self.refund_repository.get_by_provider_refund_id(
            provider=refund_result.provider,
            provider_refund_id=refund_result.provider_refund_id,
            db_session=db_session,
        )
        if refund_document is None:
            raise NotFoundException("Refund for this webhook event was not found.")

        refund = RefundRead.model_validate(refund_document)
        updated_refund = await self._apply_refund_provider_result(
            refund.id,
            refund_result,
            db_session=db_session,
        )
        updated_event = await self.payment_webhook_event_repository.update_processing_status(
            event_record.id,
            processing_status=PaymentWebhookProcessingStatuses.PROCESSED,
            processed_at=now,
            updated_at=now,
            error_message=None,
            payment_id=updated_refund.payment_id,
            order_id=updated_refund.order_id,
            refund_id=updated_refund.id,
            db_session=db_session,
        )
        event = PaymentWebhookEventRead.model_validate(updated_event or event_record)
        await self._record_audit_event(
            action="webhook.processed",
            actor_type="webhook",
            payment_id=updated_refund.payment_id,
            order_id=updated_refund.order_id,
            refund_id=updated_refund.id,
            webhook_event_id=event.id,
            provider=event.provider,
            new_status=updated_refund.status,
            db_session=db_session,
        )
        return PaymentWebhookProcessingRead(
            event_id=event.id,
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processing_status=event.processing_status,
            duplicate=False,
            payment_id=updated_refund.payment_id,
            refund_id=updated_refund.id,
            order_id=updated_refund.order_id,
            message="Refund webhook event processed.",
        )

    async def _apply_payment_webhook_result(
        self,
        *,
        payment: PaymentRead,
        payment_result: ProviderPaymentStatusResult,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> PaymentRead:
        if payment.status == payment_result.status:
            return payment
        failure_code = payment_result.failure_code
        failure_message = payment_result.failure_message
        if payment_result.status == PaymentStatuses.FAILED and not (failure_code or failure_message):
            failure_code = "provider_payment_failed"
            failure_message = "Payment provider reported failure."
        if payment_result.status == PaymentStatuses.EXPIRED and not (failure_code or failure_message):
            failure_code = "provider_payment_expired"
            failure_message = "Payment provider reported checkout expiration."

        updated = await self.payment_repository.update_status(
            payment.id,
            status=payment_result.status,
            updated_at=now,
            provider_payment_id=payment_result.provider_payment_id,
            failure_code=failure_code,
            failure_message=failure_message,
            db_session=db_session,
        )
        if updated is None:
            raise NotFoundException("Payment was not found.")
        marked = PaymentRead.model_validate(updated)
        await self._record_audit_event(
            action="payment.status_changed",
            actor_type="system",
            payment_id=marked.id,
            order_id=marked.order_id,
            provider=marked.provider,
            old_status=payment.status,
            new_status=marked.status,
            reason=failure_code or failure_message,
        )
        return marked

    async def _finalize_paid_order_from_webhook(
        self,
        order_id: str,
        *,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> None:
        order_document = await self.order_repository.get_by_id(order_id, db_session=db_session)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        if order_document["status"] in {OrderStatuses.COMPLETED, OrderStatuses.PARTIALLY_CANCELLED}:
            return
        await self.session_repository.sync_completed_sessions(
            current_time=now,
            updated_at=now,
            db_session=db_session,
        )
        await self.order_finalization_command._finalize_transaction(
            order_id=order_id,
            now=now,
            db_session=db_session,
        )

    async def _release_pending_order_from_webhook(
        self,
        order_id: str,
        *,
        payment_status: str,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> None:
        order_document = await self.order_repository.get_by_id(order_id, db_session=db_session)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        if order_document["status"] != OrderStatuses.PENDING_PAYMENT:
            return

        reserved_tickets = [
            ticket
            for ticket in await self.ticket_repository.list_by_order(order_id, db_session=db_session)
            if ticket["status"] == TicketStatuses.RESERVED
        ]
        if not reserved_tickets:
            return

        release_status = (
            TicketStatuses.CANCELLED
            if payment_status == PaymentStatuses.CANCELLED
            else TicketStatuses.EXPIRED
        )
        order_release_status = {
            PaymentStatuses.FAILED: OrderStatuses.PAYMENT_FAILED,
            PaymentStatuses.CANCELLED: OrderStatuses.PAYMENT_CANCELLED,
            PaymentStatuses.EXPIRED: OrderStatuses.EXPIRED,
        }[payment_status]
        released_count = await self.ticket_repository.update_many_status_by_order(
            order_id,
            status=release_status,
            updated_at=now,
            cancelled_at=now if release_status == TicketStatuses.CANCELLED else None,
            current_status=TicketStatuses.RESERVED,
            db_session=db_session,
        )
        if released_count != len(reserved_tickets):
            raise ConflictException("Pending order reservation changed while payment webhook was being processed.")

        seats_restored = await self.session_repository.increment_available_seats(
            str(order_document["session_id"]),
            updated_at=now,
            quantity=released_count,
            db_session=db_session,
        )
        if not seats_restored:
            raise DatabaseException("Payment webhook reservation release could not restore the session seat counter.")

        refreshed_order = await refresh_order_aggregate(
            order_id,
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            updated_at=now,
            db_session=db_session,
        )
        if refreshed_order["status"] != order_release_status:
            updated_order = await self.order_repository.update_order(
                order_id,
                updates={"status": order_release_status},
                updated_at=now,
                db_session=db_session,
            )
            if updated_order is None:
                raise DatabaseException("Payment reservation release could not update the order status.")
        logger.info(
            "Released pending reservation after terminal payment update",
            extra={
                "order_id": order_id,
                "payment_status": payment_status,
                "order_status": order_release_status,
                "released_tickets_count": released_count,
            },
        )

    def _get_webhook_transition_status(self, current_status: str, next_status: str) -> str:
        if current_status == next_status:
            return PaymentWebhookProcessingStatuses.PROCESSED
        if next_status in PAYMENT_TRANSITIONS.get(current_status, set()):
            return PaymentWebhookProcessingStatuses.PROCESSED
        if current_status in TERMINAL_PAYMENT_STATUSES:
            return PaymentWebhookProcessingStatuses.SKIPPED
        raise ConflictException(f"Payment cannot move from {current_status} to {next_status}.")

    def _hash_webhook_payload(self, raw_body: bytes) -> str:
        return hashlib.sha256(raw_body).hexdigest()

    def _safe_webhook_payload_snapshot(self, raw_body: bytes) -> dict[str, Any] | None:
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, dict):
            return None
        sanitized = self._sanitize_webhook_value(parsed)
        return validate_safe_snapshot(sanitized, field_name="payload_snapshot")

    def _sanitize_webhook_value(self, value: Any, *, depth: int = 0) -> Any:
        if depth > 4:
            return "[max_depth]"
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, nested in list(value.items())[:50]:
                key_string = str(key)
                if self._is_sensitive_snapshot_key(key_string):
                    sanitized[key_string] = "[redacted]"
                else:
                    sanitized[key_string] = self._sanitize_webhook_value(nested, depth=depth + 1)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_webhook_value(item, depth=depth + 1) for item in value[:100]]
        if isinstance(value, str):
            return value[:2000]
        if value is None or isinstance(value, int | float | bool):
            return value
        return str(value)[:2000]

    def _is_sensitive_snapshot_key(self, key: str) -> bool:
        normalized = key.lower().replace("-", "_")
        return any(marker in normalized for marker in SAFE_SENSITIVE_KEY_MARKERS)

    async def _get_payable_order(
        self,
        order_id: str,
        *,
        current_user: UserRead | None,
        now: datetime,
    ) -> dict[str, Any]:
        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        if current_user is not None:
            self._ensure_order_access(order_document, current_user=current_user)
        order_document = await self._sync_order_expiry_if_elapsed(order_document, now=now)

        status = str(order_document["status"])
        if status == OrderStatuses.COMPLETED:
            raise ConflictException("Order is already paid.")
        if status == OrderStatuses.CANCELLED:
            raise ConflictException("Cancelled orders cannot be paid.")
        if status == OrderStatuses.EXPIRED:
            raise ConflictException("Expired orders cannot be paid.")
        if status != OrderStatuses.PENDING_PAYMENT:
            raise ConflictException("Payments can only be initiated for pending payment orders.")
        if order_document.get("expires_at") is not None and order_document["expires_at"] <= now:
            raise ConflictException("Pending order reservation has expired.")
        return order_document

    async def _sync_payment_order_expiry_if_elapsed(
        self,
        payment: PaymentRead,
        *,
        now: datetime,
    ) -> PaymentRead:
        order_document = await self.order_repository.get_by_id(payment.order_id)
        if order_document is None:
            return payment
        await self._sync_order_expiry_if_elapsed(order_document, now=now)
        refreshed_payment = await self.payment_repository.get_by_id(payment.id)
        return PaymentRead.model_validate(refreshed_payment) if refreshed_payment is not None else payment

    async def _sync_order_expiry_if_elapsed(
        self,
        order_document: dict[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        order_status = str(order_document["status"])
        expires_at = order_document.get("expires_at")
        if order_status == OrderStatuses.EXPIRED:
            await expire_active_payments_for_order(
                str(order_document["id"]),
                now=now,
                payment_repository=self.payment_repository,
            )
            refreshed_order = await self.order_repository.get_by_id(str(order_document["id"]))
            return refreshed_order or order_document
        if order_status != OrderStatuses.PENDING_PAYMENT or expires_at is None or expires_at > now:
            return order_document

        await sync_expired_reservations_for_session(
            str(order_document["session_id"]),
            now=now,
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            session_repository=self.session_repository,
            payment_repository=self.payment_repository,
        )
        refreshed_order = await self.order_repository.get_by_id(str(order_document["id"]))
        return refreshed_order or order_document

    async def _build_payment_details(self, payment: PaymentRead) -> PaymentDetailsRead:
        attempts = [
            PaymentAttemptRead.model_validate(attempt)
            for attempt in await self.payment_attempt_repository.list_by_payment(payment.id)
        ]
        return PaymentDetailsRead(
            **payment.model_dump(mode="python"),
            attempts=attempts,
        )

    async def _build_admin_payment_list_item(self, payment: PaymentRead) -> AdminPaymentListItemRead:
        attempts = await self.payment_attempt_repository.list_by_payment(payment.id)
        refunds = [
            RefundRead.model_validate(refund)
            for refund in await self.refund_repository.list_by_payment(payment.id)
        ]
        order_document = await self.order_repository.get_by_id(payment.order_id)
        customer = await self._build_admin_customer(payment.user_id)
        aggregate = self._build_admin_refund_aggregate(payment, refunds)

        return AdminPaymentListItemRead(
            **payment.model_dump(mode="python"),
            attempts_count=len(attempts),
            refunds_count=len(refunds),
            order_status=str(order_document["status"]) if order_document is not None else None,
            customer_name=customer.name if customer is not None else None,
            customer_email=customer.email if customer is not None else None,
            **aggregate,
        )

    async def _build_admin_customer(self, user_id: str) -> AdminPaymentCustomerRead | None:
        if self.user_repository is None:
            return AdminPaymentCustomerRead(user_id=user_id)
        user_document = await self.user_repository.get_by_id(user_id)
        if user_document is None:
            return AdminPaymentCustomerRead(user_id=user_id)
        return AdminPaymentCustomerRead(
            user_id=user_id,
            name=str(user_document.get("name")) if user_document.get("name") else None,
            email=str(user_document.get("email")) if user_document.get("email") else None,
        )

    async def _build_admin_order_context(self, order_id: str) -> AdminPaymentOrderContextRead | None:
        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            return None

        tickets = await self.ticket_repository.list_by_order(order_id)
        seats = sorted(
            [
                f"{ticket['seat_row']}-{ticket['seat_number']}"
                for ticket in tickets
                if ticket.get("seat_row") is not None and ticket.get("seat_number") is not None
            ],
            key=lambda value: tuple(int(part) for part in value.split("-", maxsplit=1)),
        )
        session_document = await self.session_repository.get_by_id(str(order_document["session_id"]))
        movie_document = None
        if session_document is not None and self.movie_repository is not None:
            movie_document = await self.movie_repository.get_by_id(str(session_document["movie_id"]))

        return AdminPaymentOrderContextRead(
            order_id=str(order_document["id"]),
            order_status=str(order_document["status"]),
            session_id=str(order_document.get("session_id")) if order_document.get("session_id") else None,
            movie_id=str(session_document["movie_id"]) if session_document is not None else None,
            movie_title=movie_document.get("title") if movie_document is not None else None,
            session_start_time=session_document.get("start_time") if session_document is not None else None,
            session_end_time=session_document.get("end_time") if session_document is not None else None,
            session_status=str(session_document["status"]) if session_document is not None else None,
            total_price=float(order_document["total_price"]) if order_document.get("total_price") is not None else None,
            tickets_count=int(order_document.get("tickets_count") or len(tickets)),
            seats=seats,
            expires_at=order_document.get("expires_at"),
        )

    def _build_admin_refund_aggregate(
        self,
        payment: PaymentRead,
        refunds: list[RefundRead],
    ) -> dict[str, Any]:
        refunded_amount = sum(
            refund.amount_minor
            for refund in refunds
            if refund.status == RefundStatuses.SUCCEEDED
        )
        reserved_refund_amount = sum(
            refund.amount_minor
            for refund in refunds
            if refund.status in ADMIN_REFUND_RESERVED_STATUSES
        )
        remaining_refundable_amount = (
            max(payment.amount_minor - reserved_refund_amount, 0)
            if payment.status in ADMIN_REFUNDABLE_PAYMENT_STATUSES
            else 0
        )
        return {
            "refunded_amount_minor": refunded_amount,
            "remaining_refundable_amount_minor": remaining_refundable_amount,
            "refundable": bool(
                payment.provider_payment_id
                and payment.status in ADMIN_REFUNDABLE_PAYMENT_STATUSES
                and remaining_refundable_amount > 0
            ),
            "latest_refund_status": refunds[0].status if refunds else None,
        }

    async def _record_audit_event(
        self,
        *,
        action: str,
        actor_type: str,
        actor_id: str | None = None,
        payment_id: str | None = None,
        order_id: str | None = None,
        refund_id: str | None = None,
        webhook_event_id: str | None = None,
        provider: str | None = None,
        old_status: str | None = None,
        new_status: str | None = None,
        reason: str | None = None,
        safe_context: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> None:
        if self.payment_audit_event_repository is None:
            return
        event = PaymentAuditEventCreate(
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            payment_id=payment_id,
            order_id=order_id,
            refund_id=refund_id,
            webhook_event_id=webhook_event_id,
            provider=provider,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            safe_context=safe_context,
        )
        await self.payment_audit_event_repository.create_event(
            {**event.model_dump(mode="python"), "created_at": datetime.now(tz=timezone.utc)},
            db_session=db_session,
        )

    def _normalize_report_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _resolve_report_currency(
        self,
        payments: list[PaymentRead],
        refunds: list[RefundRead],
    ) -> str:
        currencies = {payment.currency for payment in payments}
        currencies.update(refund.currency for refund in refunds)
        if not currencies:
            return DEFAULT_PAYMENT_CURRENCY
        if len(currencies) > 1:
            raise ConflictException("Payment report cannot aggregate multiple currencies.")
        return next(iter(currencies))

    async def _load_report_orders(self, order_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not order_ids:
            return {}
        documents = await self.order_repository.list_by_ids(order_ids)
        return {str(document["id"]): document for document in documents}

    async def _load_report_sessions(self, session_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not session_ids:
            return {}
        documents = await self.session_repository.list_by_ids(session_ids)
        return {str(document["id"]): document for document in documents}

    async def _load_report_movies(self, movie_ids: list[str]) -> dict[str, dict[str, Any]]:
        if self.movie_repository is None or not movie_ids:
            return {}
        documents = await self.movie_repository.list_by_ids(movie_ids)
        return {str(document["id"]): document for document in documents}

    def _build_report_context(
        self,
        *,
        payment: PaymentRead,
        orders: dict[str, dict[str, Any]],
        sessions: dict[str, dict[str, Any]],
        movies: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any] | None]:
        order = orders.get(payment.order_id)
        session = None
        movie = None
        if order is not None and order.get("session_id") is not None:
            session = sessions.get(str(order["session_id"]))
        if session is not None and session.get("movie_id") is not None:
            movie = movies.get(str(session["movie_id"]))
        return {"order": order, "session": session, "movie": movie}

    def _report_order_tickets_count(self, order_document: dict[str, Any] | None) -> int:
        if order_document is None:
            return 0
        try:
            return max(int(order_document.get("tickets_count") or 0), 0)
        except (TypeError, ValueError):
            return 0

    def _ensure_session_report_aggregate(
        self,
        *,
        context: dict[str, dict[str, Any] | None],
        currency: str,
        session_aggregates: dict[str, dict[str, Any]],
    ) -> tuple[str, dict[str, Any]] | None:
        session = context["session"]
        if session is None:
            return None
        session_id = str(session["id"])
        if session_id not in session_aggregates:
            movie = context["movie"]
            session_aggregates[session_id] = {
                "session_id": session_id,
                "movie_id": str(session["movie_id"]) if session.get("movie_id") is not None else None,
                "movie_title": movie.get("title") if movie is not None else None,
                "session_start_time": session.get("start_time"),
                "session_end_time": session.get("end_time"),
                "session_status": str(session["status"]) if session.get("status") is not None else None,
                "currency": currency,
                "succeeded_payments_count": 0,
                "paid_tickets_count": 0,
                "gross_revenue_minor": 0,
                "refunded_amount_minor": 0,
            }
        return session_id, session_aggregates[session_id]

    def _ensure_movie_report_aggregate(
        self,
        *,
        context: dict[str, dict[str, Any] | None],
        currency: str,
        movie_aggregates: dict[str, dict[str, Any]],
    ) -> tuple[str, dict[str, Any]] | None:
        session = context["session"]
        if session is None or session.get("movie_id") is None:
            return None
        movie_id = str(session["movie_id"])
        if movie_id not in movie_aggregates:
            movie = context["movie"]
            movie_aggregates[movie_id] = {
                "movie_id": movie_id,
                "movie_title": movie.get("title") if movie is not None else None,
                "currency": currency,
                "succeeded_payments_count": 0,
                "paid_tickets_count": 0,
                "gross_revenue_minor": 0,
                "refunded_amount_minor": 0,
            }
        return movie_id, movie_aggregates[movie_id]

    def _add_payment_to_report_aggregates(
        self,
        *,
        payment: PaymentRead,
        context: dict[str, dict[str, Any] | None],
        currency: str,
        session_aggregates: dict[str, dict[str, Any]],
        session_order_ids: dict[str, set[str]],
        movie_aggregates: dict[str, dict[str, Any]],
        movie_order_ids: dict[str, set[str]],
        movie_session_ids: dict[str, set[str]],
    ) -> None:
        order = context["order"]
        tickets_count = self._report_order_tickets_count(order)
        session_result = self._ensure_session_report_aggregate(
            context=context,
            currency=currency,
            session_aggregates=session_aggregates,
        )
        if session_result is not None:
            session_id, aggregate = session_result
            aggregate["succeeded_payments_count"] += 1
            aggregate["gross_revenue_minor"] += payment.amount_minor
            order_ids = session_order_ids.setdefault(session_id, set())
            if order is not None and payment.order_id not in order_ids:
                order_ids.add(payment.order_id)
                aggregate["paid_tickets_count"] += tickets_count

        movie_result = self._ensure_movie_report_aggregate(
            context=context,
            currency=currency,
            movie_aggregates=movie_aggregates,
        )
        if movie_result is not None:
            movie_id, aggregate = movie_result
            aggregate["succeeded_payments_count"] += 1
            aggregate["gross_revenue_minor"] += payment.amount_minor
            session = context["session"]
            if session is not None:
                movie_session_ids.setdefault(movie_id, set()).add(str(session["id"]))
            order_ids = movie_order_ids.setdefault(movie_id, set())
            if order is not None and payment.order_id not in order_ids:
                order_ids.add(payment.order_id)
                aggregate["paid_tickets_count"] += tickets_count

    def _add_refund_to_report_aggregates(
        self,
        *,
        refund: RefundRead,
        context: dict[str, dict[str, Any] | None],
        currency: str,
        session_aggregates: dict[str, dict[str, Any]],
        movie_aggregates: dict[str, dict[str, Any]],
    ) -> None:
        session_result = self._ensure_session_report_aggregate(
            context=context,
            currency=currency,
            session_aggregates=session_aggregates,
        )
        if session_result is not None:
            _, aggregate = session_result
            aggregate["refunded_amount_minor"] += refund.amount_minor

        movie_result = self._ensure_movie_report_aggregate(
            context=context,
            currency=currency,
            movie_aggregates=movie_aggregates,
        )
        if movie_result is not None:
            _, aggregate = movie_result
            aggregate["refunded_amount_minor"] += refund.amount_minor

    def _build_report_session_read(
        self,
        aggregate: dict[str, Any],
        *,
        order_ids: set[str],
    ) -> PaymentReportSessionAggregateRead:
        gross_revenue_minor = int(aggregate["gross_revenue_minor"])
        refunded_amount_minor = int(aggregate["refunded_amount_minor"])
        return PaymentReportSessionAggregateRead(
            **aggregate,
            succeeded_orders_count=len(order_ids),
            net_revenue_minor=gross_revenue_minor - refunded_amount_minor,
        )

    def _build_report_movie_read(
        self,
        aggregate: dict[str, Any],
        *,
        order_ids: set[str],
        session_ids: set[str],
    ) -> PaymentReportMovieAggregateRead:
        gross_revenue_minor = int(aggregate["gross_revenue_minor"])
        refunded_amount_minor = int(aggregate["refunded_amount_minor"])
        return PaymentReportMovieAggregateRead(
            **aggregate,
            paid_sessions_count=len(session_ids),
            succeeded_orders_count=len(order_ids),
            net_revenue_minor=gross_revenue_minor - refunded_amount_minor,
        )

    def _admin_payment_matches_search(
        self,
        item: AdminPaymentListItemRead,
        normalized_search: str,
    ) -> bool:
        values = [
            item.id,
            item.order_id,
            item.user_id,
            item.provider,
            item.provider_payment_id,
            item.idempotency_key,
            item.status,
            item.order_status,
            item.customer_name,
            item.customer_email,
            item.latest_refund_status,
        ]
        return any(normalized_search in str(value).lower() for value in values if value)

    async def _build_initiation_response_from_payment(
        self,
        *,
        payment: PaymentRead,
        order_document: dict[str, Any],
        reused: bool,
    ) -> PaymentInitiationRead:
        attempts = await self.payment_attempt_repository.list_by_payment(payment.id)
        latest_attempt = PaymentAttemptRead.model_validate(attempts[0]) if attempts else None
        return self._build_initiation_response(
            payment=payment,
            order_document=order_document,
            attempt=latest_attempt,
            provider_result=None,
            reused=reused,
        )

    def _build_initiation_response(
        self,
        *,
        payment: PaymentRead,
        order_document: dict[str, Any],
        attempt: PaymentAttemptRead | None,
        provider_result: ProviderPaymentCreateResult | ProviderPaymentStatusResult | None,
        reused: bool,
    ) -> PaymentInitiationRead:
        snapshot = attempt.response_payload_snapshot if attempt is not None else None
        return PaymentInitiationRead(
            payment_id=payment.id,
            order_id=payment.order_id,
            provider=payment.provider,
            status=payment.status,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
            attempt_id=attempt.id if attempt is not None else None,
            attempt_status=attempt.status if attempt is not None else None,
            provider_payment_id=(
                provider_result.provider_payment_id
                if provider_result is not None
                else payment.provider_payment_id
            ),
            provider_attempt_id=(
                provider_result.provider_attempt_id
                if provider_result is not None
                else (attempt.provider_attempt_id if attempt is not None else None)
            ),
            redirect_url=(
                provider_result.redirect_url
                if provider_result is not None
                else self._snapshot_string(snapshot, "redirect_url")
            ),
            client_payload=(
                provider_result.client_payload
                if provider_result is not None
                else self._snapshot_mapping(snapshot, "client_payload")
            ),
            expires_at=order_document.get("expires_at"),
            reused=reused,
        )

    def _ensure_order_access(
        self,
        order_document: dict[str, Any],
        *,
        current_user: UserRead,
    ) -> None:
        if current_user.role != Roles.ADMIN and str(order_document["user_id"]) != current_user.id:
            raise AuthorizationException("You can only access your own orders.")

    def _ensure_payment_access(
        self,
        payment: PaymentRead,
        *,
        current_user: UserRead,
    ) -> None:
        if current_user.role != Roles.ADMIN and payment.user_id != current_user.id:
            raise AuthorizationException("You can only access your own payments.")

    def _ensure_idempotent_payment_matches_order(
        self,
        *,
        payment: PaymentRead,
        order_document: dict[str, Any],
        provider_name: str,
    ) -> None:
        if payment.order_id != str(order_document["id"]):
            raise ConflictException("Payment idempotency key is already used for another order.")
        if payment.user_id != str(order_document["user_id"]):
            raise ConflictException("Payment idempotency key is already used for another user.")
        if payment.provider != provider_name:
            raise ConflictException("Payment idempotency key is already used for another provider.")

    def _ensure_order_has_no_completed_payment(self, payments: list[dict[str, Any]]) -> None:
        paid_statuses = {
            PaymentStatuses.SUCCEEDED,
            PaymentStatuses.PARTIALLY_REFUNDED,
            PaymentStatuses.REFUNDED,
        }
        if any(payment["status"] in paid_statuses for payment in payments):
            raise ConflictException("Order already has a completed payment.")

    def _ensure_retry_is_allowed(self, payments: list[dict[str, Any]]) -> None:
        self._ensure_order_has_no_completed_payment(payments)
        if any(str(payment["status"]) in REUSABLE_PAYMENT_STATUSES for payment in payments):
            raise ConflictException("Order already has an active payment to complete or inspect.")
        if not any(str(payment["status"]) in RETRYABLE_PAYMENT_STATUSES for payment in payments):
            raise ConflictException("Order does not have a failed, cancelled, or expired payment to retry.")

    def _find_reusable_payment(
        self,
        payments: list[dict[str, Any]],
        *,
        provider_name: str,
    ) -> dict[str, Any] | None:
        reusable_payment: dict[str, Any] | None = None
        for payment in payments:
            status = str(payment["status"])
            provider = normalize_provider(str(payment["provider"]))
            if status in BLOCKING_PAYMENT_STATUSES and provider != provider_name:
                raise ConflictException("Order already has an active payment with another provider.")
            if status in REUSABLE_PAYMENT_STATUSES and provider == provider_name and reusable_payment is None:
                reusable_payment = payment
        return reusable_payment

    def _has_provider_initiation(self, payment: PaymentRead) -> bool:
        return payment.provider_payment_id is not None and payment.status in REUSABLE_PAYMENT_STATUSES

    def _normalize_idempotency_key(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not 8 <= len(normalized) <= 128:
            raise ValidationException("Idempotency key must be between 8 and 128 characters.")
        return normalized

    def _generate_payment_idempotency_key(self, *, order_id: str, provider_name: str) -> str:
        return f"payment-init-{provider_name}-{order_id}-{uuid4().hex}"

    def _build_external_order_reference(self, order_document: dict[str, Any]) -> str:
        return f"order-{order_document['id']}"

    def _build_payment_description(self, order_document: dict[str, Any]) -> str:
        return f"Cinema Showcase order {order_document['id']}"

    def _build_provider_metadata(
        self,
        *,
        payment: PaymentRead,
        order_document: dict[str, Any],
        client_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "payment_id": payment.id,
            "order_id": payment.order_id,
            "external_order_reference": self._build_external_order_reference(order_document),
            "user_id": payment.user_id,
        }
        if client_metadata:
            metadata["client"] = client_metadata
        return validate_safe_snapshot(metadata, field_name="metadata") or metadata

    def _snapshot_string(self, snapshot: dict[str, Any] | None, key: str) -> str | None:
        if not snapshot:
            return None
        value = snapshot.get(key)
        return value if isinstance(value, str) else None

    def _snapshot_mapping(self, snapshot: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
        if not snapshot:
            return None
        value = snapshot.get(key)
        return value if isinstance(value, dict) else None

    async def _get_payment_or_not_found(self, payment_id: str) -> PaymentRead:
        payment = await self.payment_repository.get_by_id(payment_id)
        if payment is None:
            raise NotFoundException("Payment was not found.")
        return PaymentRead.model_validate(payment)

    async def _get_attempt_or_not_found(self, attempt_id: str) -> PaymentAttemptRead:
        attempt = await self.payment_attempt_repository.get_by_id(attempt_id)
        if attempt is None:
            raise NotFoundException("Payment attempt was not found.")
        return PaymentAttemptRead.model_validate(attempt)

    async def _mark_payment_status(
        self,
        payment_id: str,
        status: str,
        *,
        provider_payment_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> PaymentRead:
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_transition(payment.status, status)
        updated = await self.payment_repository.update_status(
            payment.id,
            status=status,
            updated_at=datetime.now(tz=timezone.utc),
            provider_payment_id=provider_payment_id,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        if updated is None:
            raise NotFoundException("Payment was not found.")
        marked = PaymentRead.model_validate(updated)
        await self._record_audit_event(
            action="payment.status_changed",
            actor_type="system",
            payment_id=marked.id,
            order_id=marked.order_id,
            provider=marked.provider,
            old_status=payment.status,
            new_status=marked.status,
            reason=failure_code or failure_message,
        )
        return marked

    async def _mark_attempt_status(
        self,
        attempt_id: str,
        status: str,
        *,
        provider_attempt_id: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PaymentAttemptRead:
        attempt = await self._get_attempt_or_not_found(attempt_id)
        self._ensure_attempt_transition(attempt.status, status)
        updated = await self.payment_attempt_repository.update_status(
            attempt.id,
            status=status,
            updated_at=datetime.now(tz=timezone.utc),
            provider_attempt_id=provider_attempt_id,
            response_payload_snapshot=response_payload_snapshot,
            error_code=error_code,
            error_message=error_message,
        )
        if updated is None:
            raise NotFoundException("Payment attempt was not found.")
        return PaymentAttemptRead.model_validate(updated)

    def _ensure_payment_transition(self, current_status: str, next_status: str) -> None:
        if current_status == next_status:
            return
        if next_status not in PAYMENT_TRANSITIONS.get(current_status, set()):
            raise ConflictException(f"Payment cannot move from {current_status} to {next_status}.")

    def _ensure_attempt_transition(self, current_status: str, next_status: str) -> None:
        if current_status == next_status:
            return
        if next_status not in ATTEMPT_TRANSITIONS.get(current_status, set()):
            raise ConflictException(f"Payment attempt cannot move from {current_status} to {next_status}.")

    def normalize_provider(self, provider: str) -> str:
        """Expose provider normalization for future provider adapters."""
        return normalize_provider(provider)
