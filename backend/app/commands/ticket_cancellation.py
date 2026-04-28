"""Command handling transactional ticket cancellation workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.core.constants import Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import (
    AuthorizationException,
    ConflictException,
    DatabaseException,
    NotFoundException,
)
from app.db.transactions import run_transaction_with_retry
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.ticket import TicketRead
from app.schemas.user import UserRead


class TicketCancellationCommand:
    """Encapsulate the ticket cancellation use case."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        order_repository: OrderRepository,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.order_repository = order_repository

    async def execute(self, ticket_id: str, current_user: UserRead) -> TicketRead:
        """Cancel a purchased ticket and refresh the parent order aggregate."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        try:
            updated_ticket = await run_transaction_with_retry(
                lambda db_session: self._cancel_transaction(
                    ticket_id=ticket_id,
                    current_user=current_user,
                    now=now,
                    db_session=db_session,
                ),
                operation_name="cancel_ticket",
            )
        except Exception as exc:
            if isinstance(exc, (AuthorizationException, ConflictException, DatabaseException, NotFoundException)):
                raise
            raise DatabaseException("Unable to cancel the ticket.") from exc

        return TicketRead.model_validate(updated_ticket)

    async def _cancel_transaction(
        self,
        *,
        ticket_id: str,
        current_user: UserRead,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> dict[str, object]:
        ticket_document = await self.ticket_repository.get_by_id(ticket_id, db_session=db_session)
        if ticket_document is None:
            raise NotFoundException("Ticket was not found.")
        self._ensure_ticket_owner(ticket_document=ticket_document, current_user=current_user)

        session_document = await self.session_repository.get_by_id(
            ticket_document["session_id"],
            db_session=db_session,
        )
        if session_document is None:
            raise NotFoundException("Session for this ticket was not found.")

        cancellation_blocker = self._get_ticket_cancellation_blocker(
            ticket_document=ticket_document,
            session_document=session_document,
            now=now,
        )
        if cancellation_blocker is not None:
            raise ConflictException(cancellation_blocker)

        updated_ticket = await self.ticket_repository.update_status(
            ticket_id,
            status=TicketStatuses.CANCELLED,
            updated_at=now,
            cancelled_at=now,
            current_status=TicketStatuses.PURCHASED,
            db_session=db_session,
        )
        if updated_ticket is None:
            raise ConflictException("Ticket can no longer be cancelled.")

        seats_restored = await self.session_repository.increment_available_seats(
            ticket_document["session_id"],
            updated_at=now,
            db_session=db_session,
        )
        if not seats_restored:
            raise DatabaseException("Ticket cancellation could not restore the session seat counter.")

        order_id = str(ticket_document.get("order_id") or "")
        if order_id:
            await refresh_order_aggregate(
                order_id,
                order_repository=self.order_repository,
                ticket_repository=self.ticket_repository,
                updated_at=now,
                db_session=db_session,
            )

        return updated_ticket

    def _get_ticket_cancellation_blocker(
        self,
        *,
        ticket_document: dict[str, object],
        session_document: dict[str, object],
        now: datetime,
    ) -> str | None:
        if ticket_document["status"] == TicketStatuses.CANCELLED:
            return "Ticket has already been cancelled."
        if ticket_document["status"] != TicketStatuses.PURCHASED:
            return "Only purchased tickets can be cancelled."
        if ticket_document.get("checked_in_at") is not None:
            return "Checked-in tickets cannot be cancelled."
        if session_document["status"] == SessionStatuses.COMPLETED:
            return "Tickets for completed sessions cannot be cancelled."
        if session_document["status"] not in {SessionStatuses.SCHEDULED, SessionStatuses.CANCELLED}:
            return "Only tickets for scheduled or cancelled sessions can be cancelled."
        if session_document["start_time"] <= now:
            return "Tickets can only be cancelled before the session starts."
        return None

    def _ensure_ticket_owner(
        self,
        *,
        ticket_document: dict[str, object],
        current_user: UserRead,
    ) -> None:
        if current_user.role != Roles.ADMIN and ticket_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only cancel your own tickets.")
