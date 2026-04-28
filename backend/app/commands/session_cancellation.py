"""Command handling session cancellation workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.core.constants import SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, DatabaseException, NotFoundException
from app.db.transactions import run_transaction_with_retry
from app.observers.events import EventPublisher, new_session_cancelled_event
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.session import SessionRead
from app.schemas.user import UserRead


class SessionCancellationCommand:
    """Encapsulate the session cancellation use case."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        order_repository: OrderRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.order_repository = order_repository
        self.event_publisher = event_publisher

    async def execute(self, session_id: str, cancelled_by: UserRead) -> SessionRead:
        """Cancel the given session and emit a domain event."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        try:
            updated_session = await run_transaction_with_retry(
                lambda db_session: self._cancel_transaction(
                    session_id=session_id,
                    now=now,
                    db_session=db_session,
                ),
                operation_name="cancel_session",
            )
        except Exception as exc:
            if isinstance(exc, (ConflictException, DatabaseException, NotFoundException)):
                raise
            raise DatabaseException("Unable to cancel the session.") from exc

        await self.event_publisher.publish(
            new_session_cancelled_event(
                {
                    "session_id": session_id,
                    "cancelled_by": cancelled_by.id,
                }
            )
        )
        return SessionRead.model_validate(updated_session)

    async def _cancel_transaction(
        self,
        *,
        session_id: str,
        now: datetime,
        db_session: AsyncIOMotorClientSession,
    ) -> dict[str, object]:
        existing_session = await self.session_repository.get_by_id(session_id, db_session=db_session)
        if existing_session is None:
            raise NotFoundException("Session was not found.")

        cancellation_blocker = self._get_cancellation_blocker(existing_session, now=now)
        if cancellation_blocker is not None:
            raise ConflictException(cancellation_blocker)

        active_tickets = await self.ticket_repository.list_by_session(
            session_id,
            active_only=True,
            db_session=db_session,
        )
        if any(ticket.get("checked_in_at") is not None for ticket in active_tickets):
            raise ConflictException("Sessions with checked-in tickets cannot be cancelled.")

        updated_session = await self.session_repository.cancel_future_scheduled_session(
            session_id=session_id,
            current_time=now,
            updated_at=now,
            db_session=db_session,
        )
        if updated_session is not None:
            if active_tickets:
                cancelled_count = await self.ticket_repository.update_many_status_by_session(
                    session_id,
                    status=TicketStatuses.CANCELLED,
                    updated_at=now,
                    cancelled_at=now,
                    current_status=TicketStatuses.PURCHASED,
                    db_session=db_session,
                )
                if cancelled_count != len(active_tickets):
                    raise ConflictException("Session ticket cascade could not be applied consistently.")

                seats_restored = await self.session_repository.increment_available_seats(
                    session_id,
                    updated_at=now,
                    quantity=cancelled_count,
                    db_session=db_session,
                )
                if not seats_restored:
                    raise DatabaseException("Session cancellation could not restore the session seat counter.")

                affected_order_ids = sorted(
                    {
                        str(ticket["order_id"])
                        for ticket in active_tickets
                        if ticket.get("order_id")
                    }
                )
                for order_id in affected_order_ids:
                    await refresh_order_aggregate(
                        order_id,
                        order_repository=self.order_repository,
                        ticket_repository=self.ticket_repository,
                        updated_at=now,
                        db_session=db_session,
                    )
            refreshed_session = await self.session_repository.get_by_id(session_id, db_session=db_session)
            if refreshed_session is None:
                raise NotFoundException("Session was not found.")
            return refreshed_session

        latest_session = await self.session_repository.get_by_id(session_id, db_session=db_session)
        if latest_session is None:
            raise NotFoundException("Session was not found.")

        latest_blocker = self._get_cancellation_blocker(latest_session, now=now)
        raise ConflictException(latest_blocker or "Session can no longer be cancelled.")

    def _get_cancellation_blocker(self, session_document: dict[str, object], *, now: datetime) -> str | None:
        if session_document["status"] == SessionStatuses.CANCELLED:
            return "Session has already been cancelled."
        if session_document["status"] == SessionStatuses.COMPLETED:
            return "Completed sessions cannot be cancelled."
        if session_document["status"] != SessionStatuses.SCHEDULED:
            return "Only scheduled sessions can be cancelled."
        if session_document["start_time"] <= now:
            return "Only future scheduled sessions can be cancelled."
        return None
