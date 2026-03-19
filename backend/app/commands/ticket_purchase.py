"""Command handling ticket purchase workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.constants import SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.observers.events import EventPublisher, new_ticket_purchased_event
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.ticket import TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead


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

        session = await self.session_repository.get_by_id(payload.session_id)
        if session is None:
            raise NotFoundException("Session was not found.")

        now = datetime.now(tz=timezone.utc)
        if session["status"] != SessionStatuses.SCHEDULED:
            raise ConflictException("Only scheduled sessions can be purchased.")
        if session["start_time"] <= now:
            raise ConflictException("Tickets can only be purchased for future sessions.")
        if session["available_seats"] <= 0:
            raise ConflictException("There are no available seats left for this session.")

        existing_ticket = await self.ticket_repository.find_by_session_and_seat(
            session_id=payload.session_id,
            seat_row=payload.seat_row,
            seat_number=payload.seat_number,
        )
        if existing_ticket:
            raise ConflictException("Selected seat has already been purchased.")

        ticket_document = {
            "session_id": payload.session_id,
            "user_id": current_user.id,
            "seat_row": payload.seat_row,
            "seat_number": payload.seat_number,
            "price": session["price"],
            "status": TicketStatuses.PURCHASED,
            "purchased_at": now,
        }
        ticket = await self.ticket_repository.create_ticket(ticket_document)

        seats_updated = await self.session_repository.decrement_available_seats_for_purchase(
            payload.session_id,
            current_time=now,
            updated_at=now,
        )
        if not seats_updated:
            await self.ticket_repository.delete_ticket(ticket["id"])
            raise ConflictException("Session is no longer available for purchase.")

        await self.event_publisher.publish(
            new_ticket_purchased_event(
                {
                    "ticket_id": ticket["id"],
                    "session_id": payload.session_id,
                    "user_id": current_user.id,
                }
            )
        )
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
