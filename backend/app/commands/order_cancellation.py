"""Command handling full-order cancellation workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.core.constants import Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import AuthorizationException, ConflictException, DatabaseException, NotFoundException
from app.db.transactions import run_transaction_with_retry
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.user import UserRead


class OrderCancellationResult(TypedDict):
    """Return value for a successful order cancellation command."""

    order: dict[str, object]
    tickets: list[dict[str, object]]


class OrderCancellationCommand:
    """Encapsulate the full-order cancellation use case."""

    def __init__(
        self,
        order_repository: OrderRepository,
        ticket_repository: TicketRepository,
        session_repository: SessionRepository,
    ) -> None:
        self.order_repository = order_repository
        self.ticket_repository = ticket_repository
        self.session_repository = session_repository

    async def execute(self, order_id: str, current_user: UserRead) -> OrderCancellationResult:
        """Cancel all active tickets in the given order and refresh aggregates."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        try:
            return await run_transaction_with_retry(
                lambda db_session: self._cancel_transaction(
                    order_id=order_id,
                    current_user=current_user,
                    now=now,
                    db_session=db_session,
                ),
                operation_name="cancel_order",
            )
        except Exception as exc:
            if isinstance(exc, (AuthorizationException, ConflictException, DatabaseException, NotFoundException)):
                raise
            raise DatabaseException("Unable to cancel the order.") from exc

    async def _cancel_transaction(
        self,
        *,
        order_id: str,
        current_user: UserRead,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> OrderCancellationResult:
        order_document = await self.order_repository.get_by_id(order_id, db_session=db_session)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        self._ensure_order_owner(order_document=order_document, current_user=current_user)

        session_document = await self.session_repository.get_by_id(
            str(order_document["session_id"]),
            db_session=db_session,
        )
        if session_document is None:
            raise NotFoundException("Session for this order was not found.")

        ticket_documents = await self.ticket_repository.list_by_order(order_id, db_session=db_session)
        if not ticket_documents:
            raise DatabaseException("Order cancellation could not find any tickets to update.")

        active_tickets = [
            ticket
            for ticket in ticket_documents
            if ticket["status"] == TicketStatuses.PURCHASED
        ]
        cancellation_blocker = self._get_order_cancellation_blocker(
            active_tickets_count=len(active_tickets),
            session_document=session_document,
            now=now,
        )
        if cancellation_blocker is not None:
            raise ConflictException(cancellation_blocker)

        cancelled_count = await self.ticket_repository.update_many_status_by_order(
            order_id,
            status=TicketStatuses.CANCELLED,
            updated_at=now,
            cancelled_at=now,
            current_status=TicketStatuses.PURCHASED,
            db_session=db_session,
        )
        if cancelled_count != len(active_tickets):
            raise ConflictException("Order can no longer be cancelled.")

        seats_restored = await self.session_repository.increment_available_seats(
            str(order_document["session_id"]),
            updated_at=now,
            quantity=cancelled_count,
            db_session=db_session,
        )
        if not seats_restored:
            raise DatabaseException("Order cancellation could not restore the session seat counter.")

        updated_order = await refresh_order_aggregate(
            order_id,
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            updated_at=now,
            db_session=db_session,
        )
        updated_tickets = await self.ticket_repository.list_by_order(order_id, db_session=db_session)
        return {
            "order": updated_order,
            "tickets": updated_tickets,
        }

    def _get_order_cancellation_blocker(
        self,
        *,
        active_tickets_count: int,
        session_document: dict[str, object],
        now: datetime,
    ) -> str | None:
        if active_tickets_count <= 0:
            return "Order has already been cancelled."
        if session_document["status"] == SessionStatuses.COMPLETED:
            return "Orders for completed sessions cannot be cancelled."
        if session_document["status"] not in {SessionStatuses.SCHEDULED, SessionStatuses.CANCELLED}:
            return "Only orders for scheduled or cancelled sessions can be cancelled."
        if session_document["start_time"] <= now:
            return "Orders can only be cancelled before the session starts."
        return None

    def _ensure_order_owner(
        self,
        *,
        order_document: dict[str, object],
        current_user: UserRead,
    ) -> None:
        if current_user.role != Roles.ADMIN and order_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only cancel your own orders.")
