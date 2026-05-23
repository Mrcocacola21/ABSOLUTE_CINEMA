"""Domain tests for pending order reservation flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.commands.order_finalization import OrderFinalizationCommand
from app.commands.order_purchase import OrderPurchaseCommand
from app.commands.reservation_expiry import expire_stale_reservations_for_session, sync_expired_reservations_for_session
from app.core.constants import MovieStatuses, OrderStatuses, Roles, SessionStatuses, TicketStatuses
from app.core.constants import PaymentStatuses
from app.core.exceptions import ConflictException
from app.observers.events import DomainEvent
from app.schemas.order import OrderPurchaseRequest, OrderSeatInput
from app.schemas.user import UserRead
from app.services.schedule import ScheduleService

ORDER_ID = "665f0f77b7f4f8f1c3a90101"


class FakeSessionRepository:
    def __init__(self, session: dict[str, object]) -> None:
        self.session = dict(session)
        self.decremented_quantity = 0
        self.restored_quantity = 0

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime, db_session=None) -> int:
        _ = (current_time, updated_at, db_session)
        return 0

    async def get_by_id(self, session_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
        if self.session["id"] != session_id:
            return None
        return dict(self.session)

    async def decrement_available_seats_for_purchase(
        self,
        session_id: str,
        *,
        current_time: datetime,
        updated_at: datetime,
        quantity: int = 1,
        db_session=None,
    ) -> bool:
        _ = (current_time, updated_at, db_session)
        if self.session["id"] != session_id or self.session["available_seats"] < quantity:
            return False
        self.session["available_seats"] = int(self.session["available_seats"]) - quantity
        self.decremented_quantity += quantity
        return True

    async def increment_available_seats(
        self,
        session_id: str,
        *,
        updated_at: datetime,
        quantity: int = 1,
        db_session=None,
    ) -> bool:
        _ = (updated_at, db_session)
        if self.session["id"] != session_id:
            return False
        self.session["available_seats"] = int(self.session["available_seats"]) + quantity
        self.restored_quantity += quantity
        return True

    async def list_movie_ids_with_future_scheduled_sessions(self, *, current_time: datetime) -> list[str]:
        _ = current_time
        return [str(self.session["movie_id"])]


class FakeTicketRepository:
    def __init__(self, tickets: list[dict[str, object]] | None = None) -> None:
        self.tickets = [dict(ticket) for ticket in tickets or []]
        self.next_ticket_number = len(self.tickets) + 1

    async def find_by_session_and_seat(
        self,
        session_id: str,
        seat_row: int,
        seat_number: int,
        *,
        active_only: bool = True,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = db_session
        blocking_statuses = {TicketStatuses.RESERVED, TicketStatuses.PURCHASED}
        for ticket in self.tickets:
            if (
                ticket["session_id"] == session_id
                and ticket["seat_row"] == seat_row
                and ticket["seat_number"] == seat_number
                and (not active_only or ticket["status"] in blocking_statuses)
            ):
                return dict(ticket)
        return None

    async def create_ticket(self, document: dict[str, object], *, db_session=None) -> dict[str, object]:
        _ = db_session
        ticket = {**document, "id": f"ticket-{self.next_ticket_number}"}
        self.next_ticket_number += 1
        self.tickets.append(ticket)
        return dict(ticket)

    async def list_by_order(self, order_id: str, *, db_session=None) -> list[dict[str, object]]:
        _ = db_session
        return [dict(ticket) for ticket in self.tickets if ticket.get("order_id") == order_id]

    async def list_by_session(
        self,
        session_id: str,
        *,
        active_only: bool = True,
        db_session=None,
    ) -> list[dict[str, object]]:
        _ = db_session
        tickets = [ticket for ticket in self.tickets if ticket["session_id"] == session_id]
        if active_only:
            tickets = [
                ticket
                for ticket in tickets
                if ticket["status"] in {TicketStatuses.RESERVED, TicketStatuses.PURCHASED}
            ]
        return [dict(ticket) for ticket in tickets]

    async def list_expired_reserved_by_session(
        self,
        session_id: str,
        *,
        expires_before: datetime,
        db_session=None,
    ) -> list[dict[str, object]]:
        _ = db_session
        return [
            dict(ticket)
            for ticket in self.tickets
            if (
                ticket["session_id"] == session_id
                and ticket["status"] == TicketStatuses.RESERVED
                and ticket["expires_at"] <= expires_before
            )
        ]

    async def expire_reserved_tickets_by_ids(
        self,
        ticket_ids: list[str],
        *,
        updated_at: datetime,
        db_session=None,
    ) -> int:
        _ = db_session
        expired = 0
        for index, ticket in enumerate(self.tickets):
            if ticket["id"] in ticket_ids and ticket["status"] == TicketStatuses.RESERVED:
                self.tickets[index] = {
                    **ticket,
                    "status": TicketStatuses.EXPIRED,
                    "updated_at": updated_at,
                    "purchased_at": None,
                    "cancelled_at": None,
                    "checked_in_at": None,
                }
                expired += 1
        return expired

    async def mark_reserved_by_order_purchased(
        self,
        order_id: str,
        *,
        purchased_at: datetime,
        updated_at: datetime,
        db_session=None,
    ) -> int:
        _ = db_session
        updated = 0
        for index, ticket in enumerate(self.tickets):
            if (
                ticket.get("order_id") == order_id
                and ticket["status"] == TicketStatuses.RESERVED
                and ticket["expires_at"] > purchased_at
            ):
                self.tickets[index] = {
                    **ticket,
                    "status": TicketStatuses.PURCHASED,
                    "purchased_at": purchased_at,
                    "updated_at": updated_at,
                }
                updated += 1
        return updated


class FakeOrderRepository:
    def __init__(self, orders: list[dict[str, object]] | None = None) -> None:
        self.orders = {str(order["id"]): dict(order) for order in orders or []}

    async def build_order_id(self) -> str:
        return ORDER_ID

    async def create_order(self, document: dict[str, object], *, db_session=None) -> dict[str, object]:
        _ = db_session
        order = {**document, "id": str(document["_id"])}
        order.pop("_id", None)
        self.orders[str(order["id"])] = order
        return dict(order)

    async def get_by_id(self, order_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
        order = self.orders.get(order_id)
        return dict(order) if order is not None else None

    async def update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, Any],
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = db_session
        order = self.orders.get(order_id)
        if order is None:
            return None
        self.orders[order_id] = {**order, **updates, "updated_at": updated_at}
        return dict(self.orders[order_id])


class FakePaymentRepository:
    def __init__(self, payments: list[dict[str, object]] | None = None) -> None:
        self.payments = {str(payment["id"]): dict(payment) for payment in payments or []}

    async def list_by_order(self, order_id: str, *, db_session=None) -> list[dict[str, object]]:
        _ = db_session
        return [dict(payment) for payment in self.payments.values() if payment["order_id"] == order_id]

    async def update_status(
        self,
        payment_id: str,
        *,
        status: str,
        updated_at: datetime,
        failure_code: str | None = None,
        failure_message: str | None = None,
        current_statuses: set[str] | None = None,
        db_session=None,
        **_: object,
    ) -> dict[str, object] | None:
        _ = db_session
        payment = self.payments.get(payment_id)
        if payment is None:
            return None
        if current_statuses is not None and payment["status"] not in current_statuses:
            return None
        self.payments[payment_id] = {
            **payment,
            "status": status,
            "updated_at": updated_at,
            "failure_code": failure_code,
            "failure_message": failure_message,
        }
        return dict(self.payments[payment_id])


class RecordingEventPublisher:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class FakeMovieRepository:
    def __init__(self, movie: dict[str, object]) -> None:
        self.movie = dict(movie)

    async def get_by_id(self, movie_id: str) -> dict[str, object] | None:
        if self.movie["id"] != movie_id:
            return None
        return dict(self.movie)

    async def list_movies(self, *, active_only: bool = True) -> list[dict[str, object]]:
        _ = active_only
        return [dict(self.movie)]

    async def update_movie(self, movie_id: str, *, updates: dict[str, object], updated_at: datetime) -> dict[str, object]:
        _ = updated_at
        if self.movie["id"] == movie_id:
            self.movie.update(updates)
        return dict(self.movie)


async def run_without_real_transaction(callback, *, operation_name: str, **_: object):
    assert operation_name in {"purchase_order", "finalize_order_reservation"}
    return await callback(object())


def build_session(*, available_seats: int = 96) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "session-1",
        "movie_id": "movie-1",
        "start_time": now + timedelta(days=1),
        "end_time": now + timedelta(days=1, hours=2),
        "price": 250.0,
        "status": SessionStatuses.SCHEDULED,
        "total_seats": 96,
        "available_seats": available_seats,
        "created_at": now,
        "updated_at": None,
    }


def build_order(*, status: str = OrderStatuses.PENDING_PAYMENT, expires_at: datetime | None = None) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": ORDER_ID,
        "user_id": "user-1",
        "session_id": "session-1",
        "status": status,
        "total_price": 250.0,
        "tickets_count": 1,
        "expires_at": expires_at or (now + timedelta(minutes=10)),
        "created_at": now,
        "updated_at": None,
    }


def build_payment(*, status: str = PaymentStatuses.PENDING) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "payment-1",
        "order_id": ORDER_ID,
        "user_id": "user-1",
        "amount_minor": 25000,
        "currency": "UAH",
        "status": status,
        "provider": "fake",
        "provider_payment_id": "fake-pay-payment-1",
        "idempotency_key": "payment-key-1",
        "failure_code": None,
        "failure_message": None,
        "metadata": None,
        "created_at": now,
        "updated_at": None,
    }


def build_ticket(
    ticket_id: str = "ticket-1",
    *,
    status: str = TicketStatuses.RESERVED,
    expires_at: datetime | None = None,
    seat_number: int = 1,
) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": ticket_id,
        "order_id": ORDER_ID,
        "session_id": "session-1",
        "user_id": "user-1",
        "seat_row": 1,
        "seat_number": seat_number,
        "price": 250.0,
        "status": status,
        "reserved_at": now,
        "expires_at": expires_at or (now + timedelta(minutes=10)),
        "purchased_at": now if status == TicketStatuses.PURCHASED else None,
        "updated_at": None,
        "cancelled_at": None,
        "checked_in_at": None,
    }


def build_user() -> UserRead:
    now = datetime.now(tz=timezone.utc)
    return UserRead(
        id="user-1",
        name="Customer",
        email="customer@example.com",
        role=Roles.USER,
        is_active=True,
        created_at=now,
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_order_reservation_creates_pending_order_reserved_tickets_and_blocks_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.commands.order_purchase.run_transaction_with_retry", run_without_real_transaction)
    session_repository = FakeSessionRepository(build_session(available_seats=96))
    ticket_repository = FakeTicketRepository()
    order_repository = FakeOrderRepository()
    event_publisher = RecordingEventPublisher()
    command = OrderPurchaseCommand(
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        order_repository=order_repository,
        event_publisher=event_publisher,
    )

    result = await command.execute(
        payload=OrderPurchaseRequest(
            session_id="session-1",
            seats=[
                OrderSeatInput(seat_row=1, seat_number=1),
                OrderSeatInput(seat_row=1, seat_number=2),
            ],
        ),
        current_user=build_user(),
    )

    assert result["order"]["status"] == OrderStatuses.PENDING_PAYMENT
    assert result["order"]["expires_at"] > result["order"]["created_at"]
    assert {ticket["status"] for ticket in result["tickets"]} == {TicketStatuses.RESERVED}
    assert all(ticket["purchased_at"] is None for ticket in result["tickets"])
    assert session_repository.decremented_quantity == 2
    assert session_repository.session["available_seats"] == 94
    assert [event.name for event in event_publisher.events] == ["ticket_reserved", "ticket_reserved"]


@pytest.mark.asyncio
async def test_reservation_rejects_already_reserved_seat_without_decrement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.commands.order_purchase.run_transaction_with_retry", run_without_real_transaction)
    session_repository = FakeSessionRepository(build_session(available_seats=96))
    ticket_repository = FakeTicketRepository([build_ticket()])
    command = OrderPurchaseCommand(
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        order_repository=FakeOrderRepository(),
        event_publisher=RecordingEventPublisher(),
    )

    with pytest.raises(ConflictException, match="already reserved or purchased"):
        await command.execute(
            payload=OrderPurchaseRequest(session_id="session-1", seats=[OrderSeatInput(seat_row=1, seat_number=1)]),
            current_user=build_user(),
        )

    assert session_repository.decremented_quantity == 0
    assert session_repository.session["available_seats"] == 96


@pytest.mark.asyncio
async def test_expired_reservation_release_marks_tickets_expired_restores_seats_and_expires_order() -> None:
    now = datetime.now(tz=timezone.utc)
    session_repository = FakeSessionRepository(build_session(available_seats=95))
    ticket_repository = FakeTicketRepository([build_ticket(expires_at=now - timedelta(minutes=1))])
    order_repository = FakeOrderRepository([build_order(expires_at=now - timedelta(minutes=1))])
    payment_repository = FakePaymentRepository([build_payment()])

    expired_count = await expire_stale_reservations_for_session(
        "session-1",
        now=now,
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        session_repository=session_repository,
        payment_repository=payment_repository,
        db_session=object(),
    )

    assert expired_count == 1
    assert ticket_repository.tickets[0]["status"] == TicketStatuses.EXPIRED
    assert session_repository.session["available_seats"] == 96
    assert order_repository.orders[ORDER_ID]["status"] == OrderStatuses.EXPIRED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.EXPIRED
    assert payment_repository.payments["payment-1"]["failure_code"] == "reservation_expired"


@pytest.mark.asyncio
async def test_expired_reservation_cleanup_is_idempotent() -> None:
    now = datetime.now(tz=timezone.utc)
    session_repository = FakeSessionRepository(build_session(available_seats=95))
    ticket_repository = FakeTicketRepository([build_ticket(expires_at=now - timedelta(minutes=1))])
    order_repository = FakeOrderRepository([build_order(expires_at=now - timedelta(minutes=1))])

    first_count = await expire_stale_reservations_for_session(
        "session-1",
        now=now,
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        session_repository=session_repository,
        db_session=object(),
    )
    second_count = await expire_stale_reservations_for_session(
        "session-1",
        now=now,
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        session_repository=session_repository,
        db_session=object(),
    )

    assert first_count == 1
    assert second_count == 0
    assert session_repository.session["available_seats"] == 96
    assert session_repository.restored_quantity == 1


@pytest.mark.asyncio
async def test_sync_expired_reservations_runs_transactional_cleanup_when_preview_finds_expired_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(tz=timezone.utc)
    session_repository = FakeSessionRepository(build_session(available_seats=95))
    ticket_repository = FakeTicketRepository([build_ticket(expires_at=now - timedelta(minutes=1))])
    order_repository = FakeOrderRepository([build_order(expires_at=now - timedelta(minutes=1))])
    payment_repository = FakePaymentRepository([build_payment()])
    operations: list[str] = []

    async def run_expiry_transaction(callback, *, operation_name: str, **_: object):
        operations.append(operation_name)
        assert operation_name == "expire_reservations"
        return await callback(object())

    monkeypatch.setattr("app.commands.reservation_expiry.run_transaction_with_retry", run_expiry_transaction)

    expired_count = await sync_expired_reservations_for_session(
        "session-1",
        now=now,
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        session_repository=session_repository,
        payment_repository=payment_repository,
    )

    assert expired_count == 1
    assert operations == ["expire_reservations"]
    assert ticket_repository.tickets[0]["status"] == TicketStatuses.EXPIRED
    assert order_repository.orders[ORDER_ID]["status"] == OrderStatuses.EXPIRED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.EXPIRED
    assert session_repository.restored_quantity == 1


@pytest.mark.asyncio
async def test_expiry_ignores_purchased_tickets_and_succeeded_payments() -> None:
    now = datetime.now(tz=timezone.utc)
    session_repository = FakeSessionRepository(build_session(available_seats=95))
    ticket_repository = FakeTicketRepository(
        [build_ticket(status=TicketStatuses.PURCHASED, expires_at=now - timedelta(minutes=1))]
    )
    order_repository = FakeOrderRepository(
        [build_order(status=OrderStatuses.COMPLETED, expires_at=now - timedelta(minutes=1))]
    )
    payment_repository = FakePaymentRepository([build_payment(status=PaymentStatuses.SUCCEEDED)])

    expired_count = await expire_stale_reservations_for_session(
        "session-1",
        now=now,
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        session_repository=session_repository,
        payment_repository=payment_repository,
        db_session=object(),
    )

    assert expired_count == 0
    assert ticket_repository.tickets[0]["status"] == TicketStatuses.PURCHASED
    assert order_repository.orders[ORDER_ID]["status"] == OrderStatuses.COMPLETED
    assert payment_repository.payments["payment-1"]["status"] == PaymentStatuses.SUCCEEDED
    assert session_repository.restored_quantity == 0


@pytest.mark.asyncio
async def test_order_finalization_promotes_reserved_tickets_without_changing_seat_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.commands.order_finalization.run_transaction_with_retry", run_without_real_transaction)
    session_repository = FakeSessionRepository(build_session(available_seats=95))
    ticket_repository = FakeTicketRepository([build_ticket()])
    order_repository = FakeOrderRepository([build_order()])
    command = OrderFinalizationCommand(
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        session_repository=session_repository,
    )

    finalized = await command.execute(ORDER_ID)

    assert finalized["status"] == OrderStatuses.COMPLETED
    assert ticket_repository.tickets[0]["status"] == TicketStatuses.PURCHASED
    assert ticket_repository.tickets[0]["purchased_at"] is not None
    assert session_repository.session["available_seats"] == 95


@pytest.mark.asyncio
async def test_session_seat_map_marks_reserved_and_purchased_seats_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_expiry_sync(*args: object, **kwargs: object) -> int:
        _ = (args, kwargs)
        return 0

    monkeypatch.setattr("app.services.schedule.sync_expired_reservations_for_session", no_expiry_sync)
    session_repository = FakeSessionRepository(build_session(available_seats=94))
    movie_repository = FakeMovieRepository(
        {
            "id": "movie-1",
            "title": {"uk": "Фільм", "en": "Movie"},
            "description": {"uk": "Опис", "en": "Description"},
            "duration_minutes": 120,
            "poster_url": None,
            "poster_file_url": None,
            "genres": [],
            "status": MovieStatuses.ACTIVE,
            "created_at": datetime.now(tz=timezone.utc),
            "updated_at": None,
        }
    )
    service = ScheduleService(
        session_repository=session_repository,
        ticket_repository=FakeTicketRepository(
            [
                build_ticket(status=TicketStatuses.RESERVED, seat_number=1),
                build_ticket("ticket-2", status=TicketStatuses.PURCHASED, seat_number=2),
            ]
        ),
        movie_repository=movie_repository,
        order_repository=FakeOrderRepository(),
    )

    seats = await service.get_session_seats("session-1")
    by_number = {seat.number: seat for seat in seats.seats if seat.row == 1}

    assert by_number[1].is_available is False
    assert by_number[1].status == TicketStatuses.RESERVED
    assert by_number[2].is_available is False
    assert by_number[2].status == TicketStatuses.PURCHASED
    assert by_number[3].is_available is True
    assert by_number[3].status == "available"
