"""Unit tests for newly added management rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.constants import Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, ValidationException
from app.schemas.movie import MovieUpdate
from app.schemas.movie import MovieRead
from app.schemas.session import SessionCreate
from app.schemas.ticket import TicketRead
from app.schemas.user import UserRead, UserUpdate
from app.services.admin import AdminService
from app.services.ticket import TicketService


class FakeMovieRepository:
    def __init__(self, movie: dict[str, object] | None = None) -> None:
        self.movie = movie
        self.deleted_movie_id: str | None = None

    async def get_by_id(self, movie_id: str) -> dict[str, object] | None:
        if self.movie is None or self.movie["id"] != movie_id:
            return None
        return self.movie

    async def delete_movie(self, movie_id: str) -> bool:
        self.deleted_movie_id = movie_id
        return self.movie is not None and self.movie["id"] == movie_id

    async def list_movies(self, *, active_only: bool) -> list[dict[str, object]]:
        _ = active_only
        return [self.movie] if self.movie is not None else []

    async def create_movie(self, document: dict[str, object]) -> dict[str, object]:
        return document

    async def update_movie(
        self,
        movie_id: str,
        updates: dict[str, object],
        updated_at: datetime,
    ) -> dict[str, object] | None:
        _ = updated_at
        if self.movie is None or self.movie["id"] != movie_id:
            return None
        self.movie = {**self.movie, **updates}
        return self.movie

    async def list_by_ids(self, movie_ids: list[str]) -> list[dict[str, object]]:
        if self.movie is None or self.movie["id"] not in movie_ids:
            return []
        return [self.movie]


class FakeSessionRepository:
    def __init__(self, *, count_by_movie: int = 0, session: dict[str, object] | None = None) -> None:
        self._count_by_movie = count_by_movie
        self.session = session
        self.available_seats = 95

    async def count_by_movie(self, movie_id: str) -> int:
        _ = movie_id
        return self._count_by_movie

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime) -> int:
        _ = (current_time, updated_at)
        return 0

    async def find_overlapping(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        exclude_session_id: str | None = None,
    ) -> dict[str, object] | None:
        _ = (start_time, end_time, exclude_session_id)
        return None

    async def create_session(self, document: dict[str, object]) -> dict[str, object]:
        self.session = {**document, "id": "session-1"}
        return self.session

    async def get_by_id(self, session_id: str) -> dict[str, object] | None:
        if self.session is None or self.session["id"] != session_id:
            return None
        return self.session

    async def increment_available_seats(self, session_id: str, *, updated_at: datetime) -> bool:
        _ = (session_id, updated_at)
        self.available_seats += 1
        return True


class FakeTicketRepository:
    def __init__(self, ticket: dict[str, object] | None = None) -> None:
        self.ticket = ticket

    async def count_by_session(self, session_id: str, *, active_only: bool = True) -> int:
        _ = (session_id, active_only)
        return 0

    async def get_by_id(self, ticket_id: str) -> dict[str, object] | None:
        if self.ticket is None or self.ticket["id"] != ticket_id:
            return None
        return self.ticket

    async def update_status(
        self,
        ticket_id: str,
        *,
        status: str,
        updated_at: datetime,
        cancelled_at: datetime | None = None,
    ) -> dict[str, object] | None:
        _ = updated_at
        if self.ticket is None or self.ticket["id"] != ticket_id:
            return None
        self.ticket = {
            **self.ticket,
            "status": status,
            "updated_at": updated_at,
            "cancelled_at": cancelled_at,
        }
        return self.ticket


class FakeUserRepository:
    async def list_by_ids(self, user_ids: list[str]) -> list[dict[str, object]]:
        _ = user_ids
        return []


def build_admin_user() -> UserRead:
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


def build_regular_user() -> UserRead:
    now = datetime.now(tz=timezone.utc)
    return UserRead(
        id="user-1",
        name="User",
        email="user@example.com",
        role=Roles.USER,
        is_active=True,
        created_at=now,
        updated_at=None,
    )


def build_movie(movie_id: str = "movie-1", *, duration_minutes: int = 120, is_active: bool = True) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return MovieRead(
        id=movie_id,
        title="Interstellar",
        description="Sci-fi drama",
        duration_minutes=duration_minutes,
        poster_url=None,
        age_rating="PG-13",
        genres=["Sci-Fi", "Drama"],
        is_active=is_active,
        created_at=now,
        updated_at=None,
    ).model_dump(mode="python")


def build_session(session_id: str = "session-1", *, start_time: datetime | None = None) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    start = start_time or (now + timedelta(days=1))
    end = start + timedelta(minutes=120)
    return {
        "id": session_id,
        "movie_id": "movie-1",
        "start_time": start,
        "end_time": end,
        "price": 200.0,
        "status": SessionStatuses.SCHEDULED,
        "total_seats": 96,
        "available_seats": 95,
        "created_at": now,
        "updated_at": None,
    }


def build_ticket(ticket_id: str = "ticket-1") -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return TicketRead(
        id=ticket_id,
        user_id="user-1",
        session_id="session-1",
        seat_row=2,
        seat_number=5,
        price=200.0,
        status=TicketStatuses.PURCHASED,
        purchased_at=now,
        updated_at=None,
        cancelled_at=None,
    ).model_dump(mode="python")


def test_movie_update_schema_normalizes_genres_and_keeps_nullables() -> None:
    payload = MovieUpdate(
        genres=[" Drama ", "", "drama", "Comedy"],
        poster_url=None,
    )

    dumped = payload.model_dump(exclude_unset=True)

    assert dumped["genres"] == ["Drama", "Comedy"]
    assert "poster_url" in dumped
    assert dumped["poster_url"] is None


def test_user_update_requires_current_password_for_sensitive_fields() -> None:
    with pytest.raises(ValueError):
        UserUpdate(email="new@example.com")


@pytest.mark.asyncio
async def test_admin_service_prevents_deleting_movie_with_sessions() -> None:
    movie_repository = FakeMovieRepository(movie=build_movie())
    session_repository = FakeSessionRepository(count_by_movie=1)
    ticket_repository = FakeTicketRepository()
    service = AdminService(
        movie_repository=movie_repository,
        session_repository=session_repository,
        ticket_repository=ticket_repository,
    )

    with pytest.raises(ConflictException):
        await service.delete_movie("movie-1", deleted_by=build_admin_user())

    assert movie_repository.deleted_movie_id is None


@pytest.mark.asyncio
async def test_admin_service_requires_session_slot_long_enough_for_movie() -> None:
    movie_repository = FakeMovieRepository(movie=build_movie(duration_minutes=120))
    session_repository = FakeSessionRepository()
    ticket_repository = FakeTicketRepository()
    service = AdminService(
        movie_repository=movie_repository,
        session_repository=session_repository,
        ticket_repository=ticket_repository,
    )
    now = datetime.now(tz=timezone.utc) + timedelta(days=1)
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=90)

    with pytest.raises(ValidationException):
        await service.create_session(
            SessionCreate(
                movie_id="movie-1",
                start_time=start_time,
                end_time=end_time,
                price=200,
            ),
            created_by=build_admin_user(),
        )


@pytest.mark.asyncio
async def test_ticket_service_cancellation_restores_seat_counter() -> None:
    session_repository = FakeSessionRepository(session=build_session())
    ticket_repository = FakeTicketRepository(ticket=build_ticket())
    service = TicketService(
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        movie_repository=FakeMovieRepository(movie=build_movie()),
        user_repository=FakeUserRepository(),
    )

    cancelled = await service.cancel_ticket("ticket-1", current_user=build_regular_user())

    assert cancelled.status == TicketStatuses.CANCELLED
    assert cancelled.cancelled_at is not None
    assert session_repository.available_seats == 96
