"""Helpers for releasing expired pending seat reservations."""

from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.core.constants import PaymentStatuses
from app.core.exceptions import ConflictException, DatabaseException
from app.core.logging import get_logger
from app.db.transactions import run_transaction_with_retry
from app.repositories.orders import OrderRepository
from app.repositories.payments import PaymentRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository

logger = get_logger(__name__)

EXPIRABLE_PAYMENT_STATUSES = {
    PaymentStatuses.CREATED,
    PaymentStatuses.PENDING,
    PaymentStatuses.REQUIRES_ACTION,
}


async def expire_stale_reservations_for_session(
    session_id: str,
    *,
    now: datetime,
    order_repository: OrderRepository,
    ticket_repository: TicketRepository,
    session_repository: SessionRepository,
    payment_repository: PaymentRepository | None = None,
    db_session: AsyncIOMotorClientSession,
) -> int:
    """Expire elapsed reserved tickets for one session inside an existing transaction."""
    expired_tickets = await ticket_repository.list_expired_reserved_by_session(
        session_id,
        expires_before=now,
        db_session=db_session,
    )
    if not expired_tickets:
        return 0

    expired_ticket_ids = [str(ticket["id"]) for ticket in expired_tickets]
    expired_count = await ticket_repository.expire_reserved_tickets_by_ids(
        expired_ticket_ids,
        updated_at=now,
        db_session=db_session,
    )
    if expired_count != len(expired_ticket_ids):
        raise ConflictException("Expired reservations changed while release was in progress.")

    seats_restored = await session_repository.increment_available_seats(
        session_id,
        updated_at=now,
        quantity=expired_count,
        db_session=db_session,
    )
    if not seats_restored:
        raise DatabaseException("Expired reservation release could not restore the session seat counter.")

    affected_order_ids = sorted(
        {
            str(ticket["order_id"])
            for ticket in expired_tickets
            if ticket.get("order_id")
        }
    )
    for order_id in affected_order_ids:
        await refresh_order_aggregate(
            order_id,
            order_repository=order_repository,
            ticket_repository=ticket_repository,
            updated_at=now,
            db_session=db_session,
        )
        await expire_active_payments_for_order(
            order_id,
            now=now,
            payment_repository=payment_repository,
            db_session=db_session,
        )

    logger.info(
        "Expired stale seat reservations",
        extra={
            "session_id": session_id,
            "expired_tickets_count": expired_count,
            "affected_orders_count": len(affected_order_ids),
        },
    )

    return expired_count


async def expire_active_payments_for_order(
    order_id: str,
    *,
    now: datetime,
    payment_repository: PaymentRepository | None,
    db_session: AsyncIOMotorClientSession | None = None,
) -> int:
    """Mark still-active local payments expired after their reservation is released."""
    if payment_repository is None or not hasattr(payment_repository, "list_by_order"):
        return 0

    expired_count = 0
    payments = await payment_repository.list_by_order(order_id, db_session=db_session)
    for payment in payments:
        if str(payment["status"]) not in EXPIRABLE_PAYMENT_STATUSES:
            continue
        updated = await payment_repository.update_status(
            str(payment["id"]),
            status=PaymentStatuses.EXPIRED,
            updated_at=now,
            failure_code="reservation_expired",
            failure_message="Payment expired because the seat reservation timed out before success.",
            current_statuses=EXPIRABLE_PAYMENT_STATUSES,
            db_session=db_session,
        )
        if updated is None:
            continue
        expired_count += 1

    if expired_count:
        logger.info(
            "Expired active payments for released reservation",
            extra={"order_id": order_id, "expired_payments_count": expired_count},
        )
    return expired_count


async def sync_expired_reservations_for_session(
    session_id: str,
    *,
    now: datetime,
    order_repository: OrderRepository,
    ticket_repository: TicketRepository,
    session_repository: SessionRepository,
    payment_repository: PaymentRepository | None = None,
) -> int:
    """Run reservation expiry release for one session in its own transaction."""
    if not hasattr(ticket_repository, "list_expired_reserved_by_session"):
        return 0

    expired_preview = await ticket_repository.list_expired_reserved_by_session(
        session_id,
        expires_before=now,
    )
    if not expired_preview:
        return 0

    return await run_transaction_with_retry(
        lambda db_session: expire_stale_reservations_for_session(
            session_id,
            now=now,
            order_repository=order_repository,
            ticket_repository=ticket_repository,
            session_repository=session_repository,
            payment_repository=payment_repository,
            db_session=db_session,
        ),
        operation_name="expire_reservations",
    )
