"""Provider-neutral refund domain service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.core.constants import PaymentStatuses, RefundStatuses
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.payments.providers.base import (
    PaymentProvider,
    PaymentProviderError,
    ProviderRefundRequest,
    ProviderRefundResult,
)
from app.repositories.payment_audit_events import PaymentAuditEventRepository
from app.repositories.payments import PaymentRepository
from app.repositories.refunds import RefundRepository
from app.schemas.payment import PaymentAuditEventCreate, RefundCreate, RefundRead, normalize_provider, validate_safe_snapshot

logger = get_logger(__name__)

REFUND_TRANSITIONS: dict[str, set[str]] = {
    RefundStatuses.CREATED: {
        RefundStatuses.PENDING,
        RefundStatuses.SUCCEEDED,
        RefundStatuses.FAILED,
        RefundStatuses.CANCELLED,
    },
    RefundStatuses.PENDING: {
        RefundStatuses.SUCCEEDED,
        RefundStatuses.FAILED,
        RefundStatuses.CANCELLED,
    },
}
REFUND_RESERVED_STATUSES = {
    RefundStatuses.CREATED,
    RefundStatuses.PENDING,
    RefundStatuses.SUCCEEDED,
}
REFUNDABLE_PAYMENT_STATUSES = {
    PaymentStatuses.SUCCEEDED,
    PaymentStatuses.PARTIALLY_REFUNDED,
}


class RefundService:
    """Service for provider-neutral refund operations."""

    def __init__(
        self,
        refund_repository: RefundRepository,
        payment_repository: PaymentRepository,
        payment_provider: PaymentProvider | None = None,
        payment_audit_event_repository: PaymentAuditEventRepository | None = None,
    ) -> None:
        self.refund_repository = refund_repository
        self.payment_repository = payment_repository
        self.payment_provider = payment_provider
        self.payment_audit_event_repository = payment_audit_event_repository

    async def create_refund(
        self,
        *,
        payment_id: str,
        amount_minor: int,
        reason: str,
        requested_by: str = "system",
        provider_refund_id: str | None = None,
        request_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        """Create a local refund record against a succeeded payment."""
        payment = await self._get_payment_or_not_found(payment_id, db_session=db_session)
        self._ensure_payment_is_refundable(payment)
        await self._ensure_amount_is_refundable(payment=payment, amount_minor=amount_minor, db_session=db_session)

        now = datetime.now(tz=timezone.utc)
        refund_payload = RefundCreate(
            payment_id=payment_id,
            order_id=str(payment["order_id"]),
            user_id=str(payment["user_id"]),
            amount_minor=amount_minor,
            currency=str(payment["currency"]),
            provider=str(payment["provider"]),
            provider_refund_id=provider_refund_id,
            reason=reason,
            requested_by=requested_by,
            request_payload_snapshot=request_payload_snapshot,
            response_payload_snapshot=None,
        )
        created = await self.refund_repository.create_refund(
            {
                **refund_payload.model_dump(mode="python"),
                "status": RefundStatuses.CREATED,
                "failure_code": None,
                "failure_message": None,
                "created_at": now,
                "updated_at": None,
            },
            db_session=db_session,
        )
        refund = RefundRead.model_validate(created)
        await self._record_audit_event(
            action="refund.created",
            actor_type=self._actor_type(requested_by),
            actor_id=requested_by,
            payment_id=refund.payment_id,
            order_id=refund.order_id,
            refund_id=refund.id,
            provider=refund.provider,
            new_status=refund.status,
            reason=reason,
            safe_context={"amount_minor": refund.amount_minor, "currency": refund.currency},
            db_session=db_session,
        )
        return refund

    async def refund_payment(
        self,
        *,
        payment_id: str,
        amount_minor: int | None,
        reason: str,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
        fail_on_provider_error: bool = True,
    ) -> RefundRead:
        """Create a refund, call the configured provider, and persist the normalized result."""
        if self.payment_provider is None:
            raise ConflictException("Refund provider is not configured.")

        metadata = validate_safe_snapshot(metadata, field_name="metadata")
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_is_refundable(payment)
        provider_payment_id = self._require_provider_payment_id(payment)
        refund_amount_minor = await self._resolve_refund_amount(payment=payment, amount_minor=amount_minor)

        refund = await self.create_refund(
            payment_id=payment_id,
            amount_minor=refund_amount_minor,
            reason=reason,
            requested_by=requested_by,
            request_payload_snapshot={
                "operation": "refund_payment",
                "requested_amount_minor": amount_minor,
                "metadata": metadata,
            },
        )
        provider_request = ProviderRefundRequest(
            refund_id=refund.id,
            payment_id=payment_id,
            provider_payment_id=provider_payment_id,
            amount_minor=refund.amount_minor,
            currency=refund.currency,
            reason=refund.reason,
            idempotency_key=f"refund-{refund.id}",
            metadata=metadata,
        )
        await self._record_refund_request_snapshot(refund.id, provider_request)

        try:
            provider_result = await self.payment_provider.refund_payment(provider_request)
        except PaymentProviderError as exc:
            failed = await self.mark_refund_failed(
                refund.id,
                failure_code=exc.code,
                failure_message=exc.message,
                response_payload_snapshot=self._provider_error_snapshot(exc),
            )
            logger.warning(
                "Payment provider failed refund creation",
                extra={
                    "payment_id": payment_id,
                    "refund_id": refund.id,
                    "provider": normalize_provider(self.payment_provider.name),
                    "error_code": exc.code,
                },
            )
            if fail_on_provider_error:
                raise ConflictException("Payment provider failed to create refund.") from exc
            return failed

        return await self.apply_provider_result(refund.id, provider_result)

    async def refund_order_amount(
        self,
        *,
        order_id: str,
        amount_minor: int,
        reason: str,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
        cap_to_remaining: bool = False,
        fail_on_provider_error: bool = False,
    ) -> RefundRead | None:
        """Refund an amount against the latest refundable payment for an order."""
        if amount_minor <= 0:
            raise ValidationException("Refund amount must be greater than zero.")

        payment = await self._find_refundable_payment_for_order(order_id)
        if payment is None:
            return None

        remaining_amount = await self.get_remaining_refundable_amount(str(payment["id"]))
        if remaining_amount <= 0:
            return None
        refund_amount = min(amount_minor, remaining_amount) if cap_to_remaining else amount_minor
        if refund_amount <= 0:
            return None

        return await self.refund_payment(
            payment_id=str(payment["id"]),
            amount_minor=refund_amount,
            reason=reason,
            requested_by=requested_by,
            metadata=metadata,
            fail_on_provider_error=fail_on_provider_error,
        )

    async def list_payment_refunds(self, payment_id: str) -> list[RefundRead]:
        """Return refund history for one payment."""
        return [
            RefundRead.model_validate(refund)
            for refund in await self.refund_repository.list_by_payment(payment_id)
        ]

    async def list_order_refunds(self, order_id: str) -> list[RefundRead]:
        """Return refund history for one order."""
        return [
            RefundRead.model_validate(refund)
            for refund in await self.refund_repository.list_by_order(order_id)
        ]

    async def get_remaining_refundable_amount(self, payment_id: str) -> int:
        """Return paid minor units not already reserved by created/pending/succeeded refunds."""
        payment = await self._get_payment_or_not_found(payment_id)
        self._ensure_payment_is_refundable(payment)
        return await self._remaining_refundable_amount(payment)

    async def apply_provider_result(
        self,
        refund_id: str,
        provider_result: ProviderRefundResult,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        """Apply a provider-normalized refund result to the local refund record."""
        refund_document = await self.refund_repository.get_by_id(refund_id, db_session=db_session)
        if refund_document is None:
            raise NotFoundException("Refund was not found.")

        refund = RefundRead.model_validate(refund_document)
        self._ensure_refund_provider_result_matches(refund, provider_result)
        response_payload_snapshot = self._provider_result_snapshot(provider_result)

        if provider_result.status == RefundStatuses.CREATED:
            self._ensure_refund_transition(refund.status, RefundStatuses.CREATED)
            updated = await self.refund_repository.update_status(
                refund.id,
                status=RefundStatuses.CREATED,
                updated_at=datetime.now(tz=timezone.utc),
                provider_refund_id=provider_result.provider_refund_id,
                failure_code=provider_result.failure_code,
                failure_message=provider_result.failure_message,
                response_payload_snapshot=response_payload_snapshot,
                db_session=db_session,
            )
            if updated is None:
                raise NotFoundException("Refund was not found.")
            return RefundRead.model_validate(updated)
        if provider_result.status == RefundStatuses.PENDING:
            return await self.mark_refund_pending(
                refund.id,
                provider_refund_id=provider_result.provider_refund_id,
                response_payload_snapshot=response_payload_snapshot,
                db_session=db_session,
            )
        if provider_result.status == RefundStatuses.SUCCEEDED:
            return await self.mark_refund_succeeded(
                refund.id,
                provider_refund_id=provider_result.provider_refund_id,
                response_payload_snapshot=response_payload_snapshot,
                db_session=db_session,
            )
        if provider_result.status == RefundStatuses.FAILED:
            return await self.mark_refund_failed(
                refund.id,
                provider_refund_id=provider_result.provider_refund_id,
                failure_code=provider_result.failure_code or "provider_refund_failed",
                failure_message=provider_result.failure_message or "Payment provider reported refund failure.",
                response_payload_snapshot=response_payload_snapshot,
                db_session=db_session,
            )
        if provider_result.status == RefundStatuses.CANCELLED:
            return await self.mark_refund_cancelled(
                refund.id,
                provider_refund_id=provider_result.provider_refund_id,
                response_payload_snapshot=response_payload_snapshot,
                db_session=db_session,
            )

        raise ConflictException(f"Unsupported provider-normalized refund status '{provider_result.status}'.")

    async def mark_refund_pending(
        self,
        refund_id: str,
        *,
        provider_refund_id: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        """Move a refund into pending state."""
        return await self._mark_refund_status(
            refund_id,
            RefundStatuses.PENDING,
            provider_refund_id=provider_refund_id,
            response_payload_snapshot=response_payload_snapshot,
            db_session=db_session,
        )

    async def mark_refund_succeeded(
        self,
        refund_id: str,
        *,
        provider_refund_id: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        """Mark a refund as succeeded and update the payment aggregate."""
        refund = await self._mark_refund_status(
            refund_id,
            RefundStatuses.SUCCEEDED,
            provider_refund_id=provider_refund_id,
            response_payload_snapshot=response_payload_snapshot,
            db_session=db_session,
        )
        await self._refresh_payment_refund_status(refund.payment_id, db_session=db_session)
        return refund

    async def mark_refund_failed(
        self,
        refund_id: str,
        *,
        provider_refund_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        """Mark a refund as failed."""
        return await self._mark_refund_status(
            refund_id,
            RefundStatuses.FAILED,
            provider_refund_id=provider_refund_id,
            failure_code=failure_code,
            failure_message=failure_message,
            response_payload_snapshot=response_payload_snapshot,
            db_session=db_session,
        )

    async def mark_refund_cancelled(
        self,
        refund_id: str,
        *,
        provider_refund_id: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        """Mark a refund as cancelled."""
        refund = await self._mark_refund_status(
            refund_id,
            RefundStatuses.CANCELLED,
            provider_refund_id=provider_refund_id,
            response_payload_snapshot=response_payload_snapshot,
            db_session=db_session,
        )
        await self._refresh_payment_refund_status(refund.payment_id, db_session=db_session)
        return refund

    async def _get_payment_or_not_found(
        self,
        payment_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        payment = await self.payment_repository.get_by_id(payment_id, db_session=db_session)
        if payment is None:
            raise NotFoundException("Payment was not found.")
        return payment

    async def _get_refund_or_not_found(
        self,
        refund_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        refund = await self.refund_repository.get_by_id(refund_id, db_session=db_session)
        if refund is None:
            raise NotFoundException("Refund was not found.")
        return RefundRead.model_validate(refund)

    async def _mark_refund_status(
        self,
        refund_id: str,
        status: str,
        *,
        provider_refund_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> RefundRead:
        refund = await self._get_refund_or_not_found(refund_id, db_session=db_session)
        self._ensure_refund_transition(refund.status, status)
        updated = await self.refund_repository.update_status(
            refund.id,
            status=status,
            updated_at=datetime.now(tz=timezone.utc),
            provider_refund_id=provider_refund_id,
            failure_code=failure_code,
            failure_message=failure_message,
            response_payload_snapshot=response_payload_snapshot,
            db_session=db_session,
        )
        if updated is None:
            raise NotFoundException("Refund was not found.")
        marked = RefundRead.model_validate(updated)
        await self._record_audit_event(
            action="refund.status_changed",
            actor_type="system",
            payment_id=marked.payment_id,
            order_id=marked.order_id,
            refund_id=marked.id,
            provider=marked.provider,
            old_status=refund.status,
            new_status=marked.status,
            reason=failure_code or failure_message,
            safe_context={"provider_refund_id": provider_refund_id},
            db_session=db_session,
        )
        return marked

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

    def _actor_type(self, requested_by: str) -> str:
        if requested_by.startswith("admin:"):
            return "admin"
        if requested_by.startswith("user:"):
            return "user"
        if requested_by == "system" or requested_by.startswith("system"):
            return "system"
        return "system"

    async def _record_refund_request_snapshot(
        self,
        refund_id: str,
        provider_request: ProviderRefundRequest,
    ) -> None:
        snapshot = validate_safe_snapshot(
            provider_request.model_dump(mode="python", exclude_none=True),
            field_name="request_payload_snapshot",
        )
        await self.refund_repository.update_refund(
            refund_id,
            updates={"request_payload_snapshot": snapshot},
            updated_at=datetime.now(tz=timezone.utc),
        )

    async def _refresh_payment_refund_status(
        self,
        payment_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> None:
        payment = await self._get_payment_or_not_found(payment_id, db_session=db_session)
        succeeded_refunds = [
            refund
            for refund in await self.refund_repository.list_by_payment(payment_id, db_session=db_session)
            if refund["status"] == RefundStatuses.SUCCEEDED
        ]
        refunded_amount = sum(int(refund["amount_minor"]) for refund in succeeded_refunds)
        if refunded_amount <= 0:
            return

        next_status = (
            PaymentStatuses.REFUNDED
            if refunded_amount >= int(payment["amount_minor"])
            else PaymentStatuses.PARTIALLY_REFUNDED
        )
        if payment["status"] == next_status:
            return
        if payment["status"] not in {
            PaymentStatuses.SUCCEEDED,
            PaymentStatuses.PARTIALLY_REFUNDED,
            PaymentStatuses.REFUNDED,
        }:
            raise ConflictException("Refund aggregate status can only update succeeded payments.")

        await self.payment_repository.update_status(
            payment_id,
            status=next_status,
            updated_at=datetime.now(tz=timezone.utc),
            db_session=db_session,
        )
        await self._record_audit_event(
            action="payment.status_changed",
            actor_type="system",
            payment_id=payment_id,
            order_id=str(payment["order_id"]),
            provider=str(payment["provider"]),
            old_status=str(payment["status"]),
            new_status=next_status,
            reason="refund_aggregate_updated",
            safe_context={"refunded_amount_minor": refunded_amount},
            db_session=db_session,
        )

    async def _resolve_refund_amount(
        self,
        *,
        payment: dict[str, Any],
        amount_minor: int | None,
    ) -> int:
        remaining_amount = await self._remaining_refundable_amount(payment)
        if remaining_amount <= 0:
            raise ConflictException("Payment has no remaining refundable amount.")
        if amount_minor is None:
            return remaining_amount
        if amount_minor > remaining_amount:
            raise ConflictException("Refund amount exceeds the remaining refundable payment amount.")
        return amount_minor

    async def _ensure_amount_is_refundable(
        self,
        *,
        payment: dict[str, Any],
        amount_minor: int,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> None:
        remaining_amount = await self._remaining_refundable_amount(payment, db_session=db_session)
        if amount_minor > remaining_amount:
            raise ConflictException("Refund amount exceeds the remaining refundable payment amount.")

    async def _remaining_refundable_amount(
        self,
        payment: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        refunds = await self.refund_repository.list_by_payment(str(payment["id"]), db_session=db_session)
        reserved_amount = sum(
            int(refund["amount_minor"])
            for refund in refunds
            if refund["status"] in REFUND_RESERVED_STATUSES
        )
        return max(int(payment["amount_minor"]) - reserved_amount, 0)

    async def _find_refundable_payment_for_order(self, order_id: str) -> dict[str, Any] | None:
        for payment in await self.payment_repository.list_by_order(order_id):
            if payment["status"] in REFUNDABLE_PAYMENT_STATUSES:
                return payment
        return None

    def _ensure_payment_is_refundable(self, payment: dict[str, Any]) -> None:
        if payment["status"] not in REFUNDABLE_PAYMENT_STATUSES:
            raise ConflictException("Only succeeded payments can be refunded.")

    def _require_provider_payment_id(self, payment: dict[str, Any]) -> str:
        provider_payment_id = payment.get("provider_payment_id")
        if not provider_payment_id:
            raise ConflictException("Payment has not been created with a provider yet.")
        return str(provider_payment_id)

    def _ensure_refund_provider_result_matches(
        self,
        refund: RefundRead,
        provider_result: ProviderRefundResult,
    ) -> None:
        if normalize_provider(provider_result.provider) != refund.provider:
            raise ConflictException("Refund provider result does not match the local refund provider.")
        if self.payment_provider is not None and normalize_provider(provider_result.provider) != normalize_provider(
            self.payment_provider.name
        ):
            raise ConflictException("Refund provider result does not match the configured provider.")
        if provider_result.amount_minor != refund.amount_minor:
            raise ConflictException("Refund provider amount does not match the local refund.")
        if provider_result.currency != refund.currency:
            raise ConflictException("Refund provider currency does not match the local refund.")

    def _provider_result_snapshot(self, provider_result: ProviderRefundResult) -> dict[str, Any]:
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

    def _ensure_refund_transition(self, current_status: str, next_status: str) -> None:
        if current_status == next_status:
            return
        if next_status not in REFUND_TRANSITIONS.get(current_status, set()):
            raise ConflictException(f"Refund cannot move from {current_status} to {next_status}.")
