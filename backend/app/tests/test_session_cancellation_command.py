"""Unit tests for the session cancellation command."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.commands.session_cancellation import SessionCancellationCommand
from app.core.constants import Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, DatabaseException, NotFoundException
from app.observers.events import DomainEvent
from app.schemas.user import UserRead


class FakeSessionRepository:
    """In-memory session repository double for cancellation command tests."""

    def __init__(
        self,
        session: dict[str, object] | None,
        *,
        cancel_returns_none: bool = False,
        latest_after_failed_cancel: dict[str, object] | None = None,
        restore_seats: bool = True,
    ) -> None:
        self.session = dict(session) if session is not None else None
        self.cancel_returns_none = cancel_returns_none
        self.latest_after_failed_cancel = latest_after_failed_cancel
        self.restore_seats = restore_seats
        self.synced_at: datetime | None = None
        self.restored_quantity = 0

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime) -> int:
        self.synced_at = updated_at
        assert current_time == updated_at
        return 0

    async def get_by_id(self, session_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
        if self.session is None or self.session["id"] != session_id:
            return None
        return dict(self.session)

    async def cancel_future_scheduled_session(
        self,
        *,
        session_id: str,
        current_time: datetime,
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (current_time, db_session)
        if self.cancel_returns_none or self.session is None or self.session["id"] != session_id:
            if self.latest_after_failed_cancel is not None:
                self.session = dict(self.latest_after_failed_cancel)
            return None
        self.session = {
            **self.session,
            "status": SessionStatuses.CANCELLED,
            "updated_at": updated_at,
        }
        return dict(self.session)

    async def increment_available_seats(
        self,
        session_id: str,
        *,
        updated_at: datetime,
        quantity: int,
        db_session=None,
    ) -> bool:
        _ = (session_id, updated_at, db_session)
        self.restored_quantity += quantity
        if not self.restore_seats:
            return False
        if self.session is not None:
            self.session["available_seats"] = int(self.session["available_seats"]) + quantity
        return True


class FakeTicketRepository:
    """In-memory ticket repository double for cancellation command tests."""

    def __init__(self, tickets: list[dict[str, object]], *, updated_count: int | None = None) -> None:
        self.tickets = [dict(ticket) for ticket in tickets]
        self.updated_count = updated_count
        self.updated_status_calls: list[dict[str, object]] = []

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
            tickets = [ticket for ticket in tickets if ticket["status"] == TicketStatuses.PURCHASED]
        return [dict(ticket) for ticket in tickets]

    async def update_many_status_by_session(
        self,
        session_id: str,
        *,
        status: str,
        updated_at: datetime,
        cancelled_at: datetime,
        current_status: str,
        db_session=None,
    ) -> int:
        _ = db_session
        self.updated_status_calls.append(
            {
                "session_id": session_id,
                "status": status,
                "updated_at": updated_at,
                "cancelled_at": cancelled_at,
                "current_status": current_status,
            }
        )
        matching_indexes = [
            index
            for index, ticket in enumerate(self.tickets)
            if ticket["session_id"] == session_id and ticket["status"] == current_status
        ]
        if self.updated_count is not None:
            return self.updated_count
        for index in matching_indexes:
            self.tickets[index] = {
                **self.tickets[index],
                "status": status,
                "updated_at": updated_at,
                "cancelled_at": cancelled_at,
            }
        return len(matching_indexes)


class FakeOrderRepository:
    """Placeholder order repository used when aggregate refresh is monkeypatched."""


class RecordingEventPublisher:
    """Captures published domain events."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


async def run_without_real_transaction(callback, *, operation_name: str, **_: object):
    assert operation_name == "cancel_session"
    return await callback(object())


def build_session(
    *,
    status: str = SessionStatuses.SCHEDULED,
    start_time: datetime | None = None,
) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    start = start_time or (now + timedelta(days=1))
    return {
        "id": "session-1",
        "movie_id": "movie-1",
        "start_time": start,
        "end_time": start + timedelta(hours=2),
        "price": 200.0,
        "status": status,
        "total_seats": 96,
        "available_seats": 92,
        "created_at": now,
        "updated_at": None,
    }


def build_ticket(
    ticket_id: str,
    *,
    order_id: str | None = "order-1",
    checked_in_at: datetime | None = None,
) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": ticket_id,
        "order_id": order_id,
        "session_id": "session-1",
        "status": TicketStatuses.PURCHASED,
        "checked_in_at": checked_in_at,
        "updated_at": None,
        "cancelled_at": None,
        "purchased_at": now,
    }


def build_admin() -> UserRead:
    now = datetime.now(tz=timezone.utc)
    return UserRead(
        id="admin-1",
        name="Admin",
        email="admin@example.com",
        role=Roles.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=None,
    )


def build_command(
    *,
    session_repository: FakeSessionRepository,
    ticket_repository: FakeTicketRepository | None = None,
    event_publisher: RecordingEventPublisher | None = None,
) -> SessionCancellationCommand:
    return SessionCancellationCommand(
        session_repository=session_repository,
        ticket_repository=ticket_repository or FakeTicketRepository([]),
        order_repository=FakeOrderRepository(),
        event_publisher=event_publisher or RecordingEventPublisher(),
    )


@pytest.mark.asyncio
async def test_execute_cancels_future_session_cascades_tickets_and_refreshes_affected_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.commands.session_cancellation.run_transaction_with_retry",
        run_without_real_transaction,
    )
    refreshed_order_ids: list[str] = []

    async def fake_refresh_order_aggregate(order_id: str, **kwargs: object) -> dict[str, object]:
        assert kwargs["db_session"] is not None
        refreshed_order_ids.append(order_id)
        return {"id": order_id}

    monkeypatch.setattr(
        "app.commands.session_cancellation.refresh_order_aggregate",
        fake_refresh_order_aggregate,
    )
    session_repository = FakeSessionRepository(build_session())
    ticket_repository = FakeTicketRepository(
        [
            build_ticket("ticket-1", order_id="order-2"),
            build_ticket("ticket-2", order_id="order-1"),
            build_ticket("ticket-3", order_id="order-1"),
            build_ticket("ticket-4", order_id=None),
        ]
    )
    event_publisher = RecordingEventPublisher()
    command = build_command(
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        event_publisher=event_publisher,
    )

    cancelled = await command.execute("session-1", cancelled_by=build_admin())

    assert cancelled.status == SessionStatuses.CANCELLED
    assert session_repository.synced_at is not None
    assert session_repository.restored_quantity == 4
    assert all(ticket["status"] == TicketStatuses.CANCELLED for ticket in ticket_repository.tickets)
    assert refreshed_order_ids == ["order-1", "order-2"]
    assert event_publisher.events[0].name == "session_cancelled"
    assert event_publisher.events[0].payload == {
        "session_id": "session-1",
        "cancelled_by": "admin-1",
    }


@pytest.mark.parametrize(
    ("session", "expected_message"),
    [
        (None, "Session was not found."),
        (build_session(status=SessionStatuses.CANCELLED), "Session has already been cancelled."),
        (build_session(status=SessionStatuses.COMPLETED), "Completed sessions cannot be cancelled."),
        ({**build_session(), "status": "maintenance"}, "Only scheduled sessions can be cancelled."),
        (
            build_session(start_time=datetime.now(tz=timezone.utc) - timedelta(minutes=1)),
            "Only future scheduled sessions can be cancelled.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_cancel_transaction_rejects_missing_or_non_cancellable_sessions(
    session: dict[str, object] | None,
    expected_message: str,
) -> None:
    command = build_command(session_repository=FakeSessionRepository(session))

    expected_exception = NotFoundException if session is None else ConflictException
    with pytest.raises(expected_exception, match=expected_message):
        await command._cancel_transaction(
            session_id="session-1",
            now=datetime.now(tz=timezone.utc),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_cancel_transaction_rejects_session_with_checked_in_tickets() -> None:
    command = build_command(
        session_repository=FakeSessionRepository(build_session()),
        ticket_repository=FakeTicketRepository(
            [
                build_ticket("ticket-1", checked_in_at=datetime.now(tz=timezone.utc)),
            ]
        ),
    )

    with pytest.raises(ConflictException, match="checked-in tickets cannot be cancelled"):
        await command._cancel_transaction(
            session_id="session-1",
            now=datetime.now(tz=timezone.utc),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_cancel_transaction_rejects_inconsistent_ticket_cascade() -> None:
    command = build_command(
        session_repository=FakeSessionRepository(build_session()),
        ticket_repository=FakeTicketRepository(
            [
                build_ticket("ticket-1"),
                build_ticket("ticket-2"),
            ],
            updated_count=1,
        ),
    )

    with pytest.raises(ConflictException, match="cascade could not be applied consistently"):
        await command._cancel_transaction(
            session_id="session-1",
            now=datetime.now(tz=timezone.utc),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_cancel_transaction_reports_seat_restore_failure() -> None:
    command = build_command(
        session_repository=FakeSessionRepository(build_session(), restore_seats=False),
        ticket_repository=FakeTicketRepository([build_ticket("ticket-1")]),
    )

    with pytest.raises(DatabaseException, match="restore the session seat counter"):
        await command._cancel_transaction(
            session_id="session-1",
            now=datetime.now(tz=timezone.utc),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_cancel_transaction_reports_race_when_cancel_update_matches_no_document() -> None:
    session_repository = FakeSessionRepository(
        build_session(),
        cancel_returns_none=True,
        latest_after_failed_cancel={
            **build_session(),
            "status": SessionStatuses.COMPLETED,
        },
    )
    command = build_command(session_repository=session_repository)

    with pytest.raises(ConflictException, match="Completed sessions cannot be cancelled."):
        await command._cancel_transaction(
            session_id="session-1",
            now=datetime.now(tz=timezone.utc),
            db_session=object(),
        )
