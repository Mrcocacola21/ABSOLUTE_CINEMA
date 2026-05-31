"""Unit tests for order admission and check-in validation rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.core.constants import OrderStatuses, Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import AuthorizationException, ConflictException, NotFoundException
from app.schemas.order import OrderListRead, OrderTicketRead
from app.schemas.user import UserRead
from app.security.order_validation import create_order_validation_token
from app.services.order import (
    VALIDATION_STATE_ALREADY_USED,
    VALIDATION_STATE_CANCELLED,
    VALIDATION_STATE_EXPIRED,
    VALIDATION_STATE_VALID,
    OrderService,
)


class FakeSessionRepository:
    def __init__(self, sessions: list[dict[str, object]] | None = None) -> None:
        self.sessions = sessions or []

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime) -> int:
        _ = (current_time, updated_at)
        return 0

    async def list_by_ids(self, session_ids: list[str]) -> list[dict[str, object]]:
        requested_ids = set(session_ids)
        return [session for session in self.sessions if str(session["id"]) in requested_ids]


class FakeMovieRepository:
    def __init__(self, movies: list[dict[str, object]] | None = None) -> None:
        self.movies = movies or []

    async def list_by_ids(self, movie_ids: list[str]) -> list[dict[str, object]]:
        requested_ids = set(movie_ids)
        return [movie for movie in self.movies if str(movie["id"]) in requested_ids]


class FakeOrderRepository:
    def __init__(
        self,
        order: dict[str, object] | None = None,
        *,
        update_returns_none: bool = False,
    ) -> None:
        self.order = order
        self.update_returns_none = update_returns_none
        self.update_calls: list[dict[str, object]] = []

    async def get_by_id(self, order_id: str) -> dict[str, object] | None:
        if self.order is None or str(self.order["id"]) != order_id:
            return None
        return dict(self.order)

    async def update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
    ) -> dict[str, object] | None:
        self.update_calls.append(
            {
                "order_id": order_id,
                "updates": updates,
                "updated_at": updated_at,
            }
        )
        if self.order is None or self.update_returns_none:
            return None
        self.order = {**self.order, **updates, "updated_at": updated_at}
        return dict(self.order)


class FakeTicketRepository:
    def __init__(
        self,
        tickets: list[dict[str, object]] | None = None,
        *,
        check_in_count: int = 0,
    ) -> None:
        self.tickets = tickets or []
        self.check_in_count = check_in_count

    async def list_by_order(self, order_id: str) -> list[dict[str, object]]:
        return [ticket for ticket in self.tickets if str(ticket.get("order_id")) == order_id]

    async def check_in_many_by_order(
        self,
        order_id: str,
        *,
        checked_in_at: datetime,
        updated_at: datetime,
    ) -> int:
        updated_count = 0
        for ticket in self.tickets:
            if updated_count >= self.check_in_count:
                break
            if (
                str(ticket.get("order_id")) == order_id
                and ticket.get("status") == TicketStatuses.PURCHASED
                and ticket.get("checked_in_at") is None
            ):
                ticket["checked_in_at"] = checked_in_at
                ticket["updated_at"] = updated_at
                updated_count += 1
        return updated_count


def build_service() -> OrderService:
    return OrderService(
        session_repository=object(),
        ticket_repository=object(),
        movie_repository=object(),
        order_repository=object(),
    )


def build_service_with_repositories(
    *,
    sessions: list[dict[str, object]] | None = None,
    movies: list[dict[str, object]] | None = None,
    order: dict[str, object] | None = None,
    tickets: list[dict[str, object]] | None = None,
    check_in_count: int = 0,
    update_returns_none: bool = False,
) -> OrderService:
    return OrderService(
        session_repository=FakeSessionRepository(sessions),
        ticket_repository=FakeTicketRepository(tickets, check_in_count=check_in_count),
        movie_repository=FakeMovieRepository(movies),
        order_repository=FakeOrderRepository(order, update_returns_none=update_returns_none),
    )


def build_user(user_id: str = "user-1", *, role: str = Roles.USER) -> UserRead:
    now = datetime.now(tz=timezone.utc)
    return UserRead(
        id=user_id,
        name="User",
        email=f"{user_id}@example.com",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=None,
    )


def build_order_document(order_id: str = "order-1") -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": order_id,
        "user_id": "user-1",
        "session_id": "session-1",
        "status": OrderStatuses.COMPLETED,
        "total_price": 200.0,
        "tickets_count": 1,
        "created_at": now,
        "updated_at": None,
    }


def build_session_document() -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    start_time = now + timedelta(hours=2)
    return {
        "id": "session-1",
        "movie_id": "movie-1",
        "start_time": start_time,
        "end_time": start_time + timedelta(hours=2),
        "price": 200.0,
        "status": SessionStatuses.SCHEDULED,
        "total_seats": 96,
        "available_seats": 95,
        "created_at": now,
        "updated_at": None,
    }


def build_movie_document() -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "movie-1",
        "title": {"uk": "Movie", "en": "Movie"},
        "description": {"uk": "Description", "en": "Description"},
        "duration_minutes": 120,
        "poster_url": None,
        "age_rating": "PG-13",
        "genres": ["drama"],
        "status": "active",
        "created_at": now,
        "updated_at": None,
    }


def build_ticket_document(*, order_id: str = "order-1", status: str = TicketStatuses.PURCHASED) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "ticket-1",
        "order_id": order_id,
        "seat_row": 1,
        "seat_number": 1,
        "price": 200.0,
        "status": status,
        "purchased_at": now,
        "updated_at": None,
        "cancelled_at": now if status == TicketStatuses.CANCELLED else None,
        "checked_in_at": None,
    }


def build_ticket(
    *,
    status: str = TicketStatuses.PURCHASED,
    checked_in_at: datetime | None = None,
    valid_for_entry: bool = True,
) -> OrderTicketRead:
    now = datetime.now(tz=timezone.utc)
    cancelled_at = now if status == TicketStatuses.CANCELLED else None
    return OrderTicketRead(
        id="ticket-1",
        order_id="order-1",
        seat_row=1,
        seat_number=1,
        price=200.0,
        status=status,
        purchased_at=now,
        updated_at=None,
        cancelled_at=cancelled_at,
        checked_in_at=checked_in_at,
        is_cancellable=False,
        valid_for_entry=valid_for_entry,
    )


def build_order(
    *,
    status: str = OrderStatuses.COMPLETED,
    session_status: str = SessionStatuses.SCHEDULED,
    session_start_time: datetime | None = None,
    active_tickets_count: int = 1,
    checked_in_tickets_count: int = 0,
    unchecked_active_tickets_count: int = 1,
    tickets: list[OrderTicketRead] | None = None,
) -> OrderListRead:
    now = datetime.now(tz=timezone.utc)
    start_time = session_start_time or (now + timedelta(hours=2))
    return OrderListRead(
        id="order-1",
        user_id="user-1",
        session_id="session-1",
        status=status,
        total_price=200.0,
        tickets_count=max(active_tickets_count, 1),
        created_at=now,
        updated_at=None,
        movie_id="movie-1",
        movie_title={"uk": "Movie", "en": "Movie"},
        poster_url=None,
        age_rating=None,
        session_start_time=start_time,
        session_end_time=start_time + timedelta(hours=2),
        session_price=200.0,
        session_status=session_status,
        active_tickets_count=active_tickets_count,
        cancelled_tickets_count=0 if active_tickets_count else 1,
        checked_in_tickets_count=checked_in_tickets_count,
        unchecked_active_tickets_count=unchecked_active_tickets_count,
        tickets=tickets or [build_ticket()],
    )


@pytest.mark.parametrize(
    ("order", "expected_state", "expected_message"),
    [
        (
            build_order(status=OrderStatuses.CANCELLED),
            VALIDATION_STATE_CANCELLED,
            "fully cancelled",
        ),
        (
            build_order(active_tickets_count=0, unchecked_active_tickets_count=0),
            VALIDATION_STATE_CANCELLED,
            "no active purchased tickets",
        ),
        (
            build_order(session_status=SessionStatuses.CANCELLED),
            VALIDATION_STATE_CANCELLED,
            "session was cancelled",
        ),
        (
            build_order(checked_in_tickets_count=1, unchecked_active_tickets_count=0),
            VALIDATION_STATE_ALREADY_USED,
            "already checked in",
        ),
        (
            build_order(session_status=SessionStatuses.COMPLETED),
            VALIDATION_STATE_EXPIRED,
            "already completed",
        ),
        (
            build_order(session_status="maintenance"),
            VALIDATION_STATE_EXPIRED,
            "not available",
        ),
        (
            build_order(session_start_time=datetime.now(tz=timezone.utc) - timedelta(minutes=1)),
            VALIDATION_STATE_EXPIRED,
            "already started",
        ),
        (
            build_order(tickets=[build_ticket(valid_for_entry=False)]),
            VALIDATION_STATE_ALREADY_USED,
            "no unchecked tickets",
        ),
    ],
)
def test_get_order_validity_explains_each_blocked_entry_state(
    order: OrderListRead,
    expected_state: str,
    expected_message: str,
) -> None:
    is_valid, state, message = build_service()._get_order_validity(
        order=order,
        now=datetime.now(tz=timezone.utc),
    )

    assert is_valid is False
    assert state == expected_state
    assert expected_message in message


def test_get_order_validity_allows_future_scheduled_order_with_unchecked_ticket() -> None:
    is_valid, state, message = build_service()._get_order_validity(
        order=build_order(),
        now=datetime.now(tz=timezone.utc),
    )

    assert is_valid is True
    assert state == VALIDATION_STATE_VALID
    assert "future scheduled session" in message


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (VALIDATION_STATE_ALREADY_USED, "already been checked in"),
        (VALIDATION_STATE_CANCELLED, "cannot be checked in"),
        (VALIDATION_STATE_EXPIRED, "Expired orders"),
        ("unknown", "Order cannot be checked in."),
    ],
)
def test_get_check_in_blocker_message_maps_validation_state_to_staff_error(
    state: str,
    message: str,
) -> None:
    assert message in build_service()._get_check_in_blocker_message(state)


def test_ensure_order_owner_rejects_admin_self_service_access() -> None:
    with pytest.raises(AuthorizationException, match="only access your own orders"):
        build_service()._ensure_order_owner(
            order_document={"user_id": "user-1"},
            current_user=build_user("admin-1", role=Roles.ADMIN),
        )


def test_ensure_order_owner_rejects_other_regular_users_orders() -> None:
    with pytest.raises(AuthorizationException, match="only access your own orders"):
        build_service()._ensure_order_owner(
            order_document={"user_id": "owner-1"},
            current_user=build_user("user-1"),
        )


@pytest.mark.asyncio
async def test_get_current_user_order_reports_missing_order() -> None:
    service = build_service_with_repositories()

    with pytest.raises(NotFoundException, match="Order was not found."):
        await service.get_current_user_order("missing-order", current_user=build_user())


@pytest.mark.parametrize(
    ("sessions", "movies", "tickets"),
    [
        ([], [build_movie_document()], [build_ticket_document()]),
        ([build_session_document()], [], [build_ticket_document()]),
        ([build_session_document()], [build_movie_document()], []),
    ],
)
@pytest.mark.asyncio
async def test_build_order_list_skips_orders_when_required_linked_data_is_missing(
    sessions: list[dict[str, object]],
    movies: list[dict[str, object]],
    tickets: list[dict[str, object]],
) -> None:
    service = build_service_with_repositories(sessions=sessions, movies=movies, tickets=tickets)

    built_orders = await service._build_order_list(
        [build_order_document()],
        now=datetime.now(tz=timezone.utc),
    )

    assert built_orders == []


@pytest.mark.asyncio
async def test_get_current_user_order_reports_unavailable_order_when_linked_data_is_missing() -> None:
    service = build_service_with_repositories(order=build_order_document())

    with pytest.raises(NotFoundException, match="Order was not found."):
        await service.get_current_user_order("order-1", current_user=build_user())


@pytest.mark.asyncio
async def test_validate_order_token_returns_unavailable_when_linked_data_is_missing() -> None:
    order_id = str(ObjectId())
    service = build_service_with_repositories(order=build_order_document(order_id))

    validation = await service.validate_order_token(
        create_order_validation_token(order_id),
        requested_by=build_user("admin-1", role=Roles.ADMIN),
    )

    assert validation.token_status == "order_unavailable"
    assert validation.validity_code == "order_unavailable"
    assert validation.order_id == order_id


@pytest.mark.asyncio
async def test_validate_order_token_returns_current_validation_shape_without_legacy_entry_status() -> None:
    order_id = str(ObjectId())
    service = build_service_with_repositories(
        sessions=[build_session_document()],
        movies=[build_movie_document()],
        order=build_order_document(order_id),
        tickets=[build_ticket_document(order_id=order_id)],
    )

    validation = await service.validate_order_token(
        create_order_validation_token(order_id),
        requested_by=build_user("admin-1", role=Roles.ADMIN),
    )
    payload = validation.model_dump(mode="json")

    assert validation.token_status == "valid_token"
    assert validation.validity_code == VALIDATION_STATE_VALID
    assert validation.can_check_in is True
    assert "validity_code" in payload
    assert "entry_status_code" not in payload


@pytest.mark.asyncio
async def test_synchronize_order_aggregate_falls_back_to_derived_fields_when_update_returns_none() -> None:
    service = build_service_with_repositories(
        order=build_order_document(),
        update_returns_none=True,
    )

    synchronized = await service._synchronize_order_aggregate(
        order_document=build_order_document(),
        ticket_documents=[build_ticket_document(status=TicketStatuses.CANCELLED)],
        updated_at=datetime.now(tz=timezone.utc),
    )

    assert synchronized["status"] == OrderStatuses.CANCELLED
    assert synchronized["updated_at"] is not None


@pytest.mark.asyncio
async def test_check_in_order_reports_repeat_when_no_tickets_are_updated() -> None:
    service = build_service_with_repositories(
        sessions=[build_session_document()],
        movies=[build_movie_document()],
        order=build_order_document(),
        tickets=[build_ticket_document()],
        check_in_count=0,
    )

    with pytest.raises(ConflictException, match="already been checked in"):
        await service.check_in_order("order-1", requested_by=build_user("admin-1", role=Roles.ADMIN))


@pytest.mark.asyncio
async def test_check_in_order_returns_current_validation_shape_without_legacy_entry_status() -> None:
    order_id = str(ObjectId())
    service = build_service_with_repositories(
        sessions=[build_session_document()],
        movies=[build_movie_document()],
        order=build_order_document(order_id),
        tickets=[build_ticket_document(order_id=order_id)],
        check_in_count=1,
    )

    validation = await service.check_in_order(order_id, requested_by=build_user("admin-1", role=Roles.ADMIN))
    payload = validation.model_dump(mode="json")

    assert validation.validity_code == VALIDATION_STATE_ALREADY_USED
    assert validation.is_valid_for_entry is False
    assert validation.can_check_in is False
    assert validation.checked_in_tickets_count == 1
    assert "validity_code" in payload
    assert "entry_status_code" not in payload
