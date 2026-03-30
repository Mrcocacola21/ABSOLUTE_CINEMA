"""Command handling ticket purchase workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.constants import SessionStatuses, TicketStatuses
from app.core.exceptions import (
    ConflictException,
    DatabaseException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.observers.events import EventPublisher, new_ticket_purchased_event
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.ticket import TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead

logger = get_logger(__name__)


class TicketPurchaseCommand:
    """Encapsulate the ticket purchasing use case."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.event_publisher = event_publisher

    async def execute(self, payload: TicketPurchaseRequest, current_user: UserRead) -> TicketRead:
        """Purchase a ticket if the seat is still available."""
        settings = get_settings()
        self._validate_seat_coordinates(
            payload=payload,
            rows_count=settings.hall_rows_count,
            seats_per_row=settings.hall_seats_per_row,
        )

        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        session = await self.session_repository.get_by_id(payload.session_id)
        if session is None:
            raise NotFoundException("Session was not found.")

        purchase_blocker = self._get_purchase_blocker(session=session, now=now)
        if purchase_blocker is not None:
            raise ConflictException(purchase_blocker)

        existing_ticket = await self.ticket_repository.find_by_session_and_seat(
            session_id=payload.session_id,
            seat_row=payload.seat_row,
            seat_number=payload.seat_number,
        )
        if existing_ticket:
            raise ConflictException("Selected seat has already been purchased.")

        seats_reserved = await self.session_repository.decrement_available_seats_for_purchase(
            payload.session_id,
            current_time=now,
            updated_at=now,
        )
        if not seats_reserved:
            latest_session = await self.session_repository.get_by_id(payload.session_id)
            if latest_session is None:
                raise NotFoundException("Session was not found.")
            latest_purchase_blocker = self._get_purchase_blocker(session=latest_session, now=now)
            raise ConflictException(latest_purchase_blocker or "Session is no longer available for purchase.")

        ticket_document = {
            "session_id": payload.session_id,
            "user_id": current_user.id,
            "seat_row": payload.seat_row,
            "seat_number": payload.seat_number,
            "price": session["price"],
            "status": TicketStatuses.PURCHASED,
            "purchased_at": now,
            "updated_at": None,
            "cancelled_at": None,
        }
        try:
            ticket = await self.ticket_repository.create_ticket(ticket_document)
        except Exception as exc:
            restored = await self._restore_reserved_seat(payload.session_id, updated_at=now)
            if not restored:
                raise DatabaseException(
                    "Ticket purchase failed and the session seat counter could not be restored."
                ) from exc
            raise

        try:
            await self.event_publisher.publish(
                new_ticket_purchased_event(
                    {
                        "ticket_id": ticket["id"],
                        "session_id": payload.session_id,
                        "user_id": current_user.id,
                    }
                )
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.exception("Ticket purchase event publication failed", exc_info=exc)
        return TicketRead.model_validate(ticket)

    def _validate_seat_coordinates(
        self,
        *,
        payload: TicketPurchaseRequest,
        rows_count: int,
        seats_per_row: int,
    ) -> None:
        if payload.seat_row > rows_count or payload.seat_number > seats_per_row:
            raise ValidationException("Seat coordinates are outside the configured hall dimensions.")

    def _get_purchase_blocker(
        self,
        *,
        session: dict[str, object],
        now: datetime,
    ) -> str | None:
        if session["status"] == SessionStatuses.CANCELLED:
            return "Cancelled sessions cannot be purchased."
        if session["status"] == SessionStatuses.COMPLETED:
            return "Completed sessions cannot be purchased."
        if session["status"] != SessionStatuses.SCHEDULED:
            return "Only scheduled sessions can be purchased."
        if session["start_time"] <= now:
            return "Past sessions cannot be purchased."
        if session["available_seats"] <= 0:
            return "There are no available seats left for this session."
        return None

    async def _restore_reserved_seat(self, session_id: str, *, updated_at: datetime) -> bool:
        seats_restored = await self.session_repository.increment_available_seats(
            session_id,
            updated_at=updated_at,
        )
        if seats_restored:
            return True
        if await self._session_counter_matches_active_tickets(session_id):
            return True
        return await self._reconcile_available_seats(session_id, updated_at=updated_at)

    async def _session_counter_matches_active_tickets(self, session_id: str) -> bool:
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            return False

        active_ticket_count = await self.ticket_repository.count_by_session(session_id, active_only=True)
        expected_available_seats = session["total_seats"] - active_ticket_count
        return session["available_seats"] == expected_available_seats

    async def _reconcile_available_seats(self, session_id: str, *, updated_at: datetime) -> bool:
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            logger.error("Unable to reconcile seats for missing session %s", session_id)
            return False

        active_ticket_count = await self.ticket_repository.count_by_session(session_id, active_only=True)
        expected_available_seats = session["total_seats"] - active_ticket_count
        repaired_session = await self.session_repository.set_available_seats(
            session_id,
            available_seats=max(expected_available_seats, 0),
            updated_at=updated_at,
        )
        if repaired_session is None:
            logger.error("Unable to reconcile available seats for session %s", session_id)
            return False
        return True
