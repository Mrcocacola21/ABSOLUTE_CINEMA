"""Command for finalizing a pending order after a future successful payment."""

from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.commands.reservation_expiry import expire_stale_reservations_for_session
from app.core.constants import OrderStatuses, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, DatabaseException, NotFoundException
from app.db.transactions import run_transaction_with_retry
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository


class OrderFinalizationCommand:
    """Promote a valid pending reservation to purchased tickets."""

    def __init__(
        self,
        order_repository: OrderRepository,
        ticket_repository: TicketRepository,
        session_repository: SessionRepository,
    ) -> None:
        self.order_repository = order_repository
        self.ticket_repository = ticket_repository
        self.session_repository = session_repository

    async def execute(self, order_id: str) -> dict[str, object]:
        """Finalize a pending order without integrating a payment provider."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        try:
            return await run_transaction_with_retry(
                lambda db_session: self._finalize_transaction(
                    order_id=order_id,
                    now=now,
                    db_session=db_session,
                ),
                operation_name="finalize_order_reservation",
            )
        except Exception as exc:
            if isinstance(exc, (ConflictException, DatabaseException, NotFoundException)):
                raise
            raise DatabaseException("Unable to finalize the pending order.") from exc

    async def _finalize_transaction(
        self,
        *,
        order_id: str,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> dict[str, object]:
        order_document = await self.order_repository.get_by_id(order_id, db_session=db_session)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        if order_document["status"] != OrderStatuses.PENDING_PAYMENT:
            raise ConflictException("Only pending payment orders can be finalized.")
        if order_document.get("expires_at") is not None and order_document["expires_at"] <= now:
            await expire_stale_reservations_for_session(
                str(order_document["session_id"]),
                now=now,
                order_repository=self.order_repository,
                ticket_repository=self.ticket_repository,
                session_repository=self.session_repository,
                db_session=db_session,
            )
            raise ConflictException("Pending order reservation has expired.")

        session_document = await self.session_repository.get_by_id(
            str(order_document["session_id"]),
            db_session=db_session,
        )
        if session_document is None:
            raise NotFoundException("Session for this order was not found.")
        if session_document["status"] != SessionStatuses.SCHEDULED or session_document["start_time"] <= now:
            raise ConflictException("Pending order can no longer be finalized for this session.")

        ticket_documents = await self.ticket_repository.list_by_order(order_id, db_session=db_session)
        reserved_tickets = [
            ticket
            for ticket in ticket_documents
            if ticket["status"] == TicketStatuses.RESERVED
        ]
        if len(reserved_tickets) != len(ticket_documents):
            raise ConflictException("Only fully reserved pending orders can be finalized.")
        if any(ticket.get("expires_at") is not None and ticket["expires_at"] <= now for ticket in reserved_tickets):
            raise ConflictException("Pending order reservation has expired.")

        updated_count = await self.ticket_repository.mark_reserved_by_order_purchased(
            order_id,
            purchased_at=now,
            updated_at=now,
            db_session=db_session,
        )
        if updated_count != len(reserved_tickets):
            raise ConflictException("Pending order tickets could not be finalized consistently.")

        return await refresh_order_aggregate(
            order_id,
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            updated_at=now,
            db_session=db_session,
        )
