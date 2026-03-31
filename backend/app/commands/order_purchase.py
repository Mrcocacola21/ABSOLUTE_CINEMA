"""Command handling multi-ticket order purchase workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from bson import ObjectId

from app.core.config import get_settings
from app.core.constants import OrderStatuses, SessionStatuses, TicketStatuses
from app.core.exceptions import (
    ConflictException,
    DatabaseException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.db.transactions import mongo_transaction
from app.observers.events import EventPublisher, new_ticket_purchased_event
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.order import OrderPurchaseRequest
from app.schemas.user import UserRead

logger = get_logger(__name__)


class OrderPurchaseResult(TypedDict):
    """Return value for a successful order purchase command."""

    order: dict[str, object]
    tickets: list[dict[str, object]]


class OrderPurchaseCommand:
    """Encapsulate the multi-ticket order purchasing use case."""

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

    async def execute(self, payload: OrderPurchaseRequest, current_user: UserRead) -> OrderPurchaseResult:
        """Purchase multiple seats for one session as one order."""
        settings = get_settings()
        self._validate_seat_coordinates(
            payload=payload,
            rows_count=settings.hall_rows_count,
            seats_per_row=settings.hall_seats_per_row,
        )

        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        try:
            order_id = str(ObjectId())
            created_order: dict[str, object] | None = None
            created_tickets: list[dict[str, object]] = []

            async with mongo_transaction() as db_session:
                session = await self.session_repository.get_by_id(payload.session_id, db_session=db_session)
                if session is None:
                    raise NotFoundException("Session was not found.")

                purchase_blocker = self._get_purchase_blocker(
                    session=session,
                    now=now,
                    requested_tickets_count=len(payload.seats),
                )
                if purchase_blocker is not None:
                    raise ConflictException(purchase_blocker)

                for seat in payload.seats:
                    existing_ticket = await self.ticket_repository.find_by_session_and_seat(
                        session_id=payload.session_id,
                        seat_row=seat.seat_row,
                        seat_number=seat.seat_number,
                        db_session=db_session,
                    )
                    if existing_ticket:
                        raise ConflictException(self._seat_conflict_message(len(payload.seats)))

                seats_reserved = await self.session_repository.decrement_available_seats_for_purchase(
                    payload.session_id,
                    current_time=now,
                    updated_at=now,
                    quantity=len(payload.seats),
                    db_session=db_session,
                )
                if not seats_reserved:
                    raise ConflictException("Session is no longer available for purchase.")

                created_order = await self.order_repository.create_order(
                    {
                        "_id": ObjectId(order_id),
                        "user_id": current_user.id,
                        "session_id": payload.session_id,
                        "status": OrderStatuses.COMPLETED,
                        "total_price": session["price"] * len(payload.seats),
                        "tickets_count": len(payload.seats),
                        "created_at": now,
                        "updated_at": None,
                    },
                    db_session=db_session,
                )

                for seat in payload.seats:
                    created_ticket = await self.ticket_repository.create_ticket(
                        {
                            "order_id": order_id,
                            "session_id": payload.session_id,
                            "user_id": current_user.id,
                            "seat_row": seat.seat_row,
                            "seat_number": seat.seat_number,
                            "price": session["price"],
                            "status": TicketStatuses.PURCHASED,
                            "purchased_at": now,
                            "updated_at": None,
                            "cancelled_at": None,
                        },
                        db_session=db_session,
                    )
                    created_tickets.append(created_ticket)
        except Exception as exc:
            if isinstance(exc, (ConflictException, ValidationException, NotFoundException, DatabaseException)):
                raise
            raise DatabaseException("Unable to complete the ticket purchase order.") from exc

        for ticket in created_tickets:
            try:
                await self.event_publisher.publish(
                    new_ticket_purchased_event(
                        {
                            "ticket_id": ticket["id"],
                            "order_id": order_id,
                            "session_id": payload.session_id,
                            "user_id": current_user.id,
                        }
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive logging path
                logger.exception("Ticket purchase event publication failed", exc_info=exc)

        return {
            "order": created_order or {},
            "tickets": created_tickets,
        }

    def _validate_seat_coordinates(
        self,
        *,
        payload: OrderPurchaseRequest,
        rows_count: int,
        seats_per_row: int,
    ) -> None:
        for seat in payload.seats:
            if seat.seat_row > rows_count or seat.seat_number > seats_per_row:
                raise ValidationException("Seat coordinates are outside the configured hall dimensions.")

    def _get_purchase_blocker(
        self,
        *,
        session: dict[str, object],
        now: datetime,
        requested_tickets_count: int,
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
        if session["available_seats"] < requested_tickets_count:
            return "There are not enough available seats left for this session."
        return None

    def _seat_conflict_message(self, requested_tickets_count: int) -> str:
        if requested_tickets_count == 1:
            return "Selected seat has already been purchased."
        return "One or more selected seats have already been purchased."
