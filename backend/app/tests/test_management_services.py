"""Unit tests for newly added management rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.constants import MovieStatuses, Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, ValidationException
from app.schemas.localization import LocalizedText
from app.schemas.movie import MovieUpdate
from app.schemas.movie import MovieRead
from app.schemas.movie import MovieCreate
from app.schemas.session import SessionCreate
from app.schemas.ticket import TicketRead
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.admin import AdminService
from app.services.order import OrderService
from app.services.ticket import TicketService


class FakeOrderRepository:
    async def list_by_ids(self, order_ids: list[str], *, db_session=None) -> list[dict[str, object]]:
        _ = (order_ids, db_session)
        return []

    async def get_by_id(
        self,
        order_id: str,
        *,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (order_id, db_session)
        return None

    async def update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (order_id, updates, updated_at, db_session)
        return None


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

    async def has_future_scheduled_sessions(self, movie_id: str, *, current_time: datetime) -> bool:
        if self.session is None or self.session["movie_id"] != movie_id:
            return False
        return self.session["status"] == SessionStatuses.SCHEDULED and self.session["start_time"] > current_time

    async def list_movie_ids_with_future_scheduled_sessions(self, *, current_time: datetime) -> list[str]:
        if self.session is None:
            return []
        if self.session["status"] != SessionStatuses.SCHEDULED or self.session["start_time"] <= current_time:
            return []
        return [str(self.session["movie_id"])]

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

    async def get_by_id(self, session_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
        if self.session is None or self.session["id"] != session_id:
            return None
        return self.session

    async def increment_available_seats(
        self,
        session_id: str,
        *,
        updated_at: datetime,
        quantity: int = 1,
        db_session=None,
    ) -> bool:
        _ = (session_id, updated_at, db_session)
        self.available_seats += quantity
        return True

    async def set_available_seats(
        self,
        session_id: str,
        *,
        available_seats: int,
        updated_at: datetime,
    ) -> dict[str, object] | None:
        _ = (updated_at,)
        if self.session is None or self.session["id"] != session_id:
            return None
        self.available_seats = available_seats
        self.session = {
            **self.session,
            "available_seats": available_seats,
        }
        return self.session

    async def cancel_future_scheduled_session(
        self,
        session_id: str,
        *,
        current_time: datetime,
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (current_time, updated_at, db_session)
        if self.session is None or self.session["id"] != session_id:
            return None
        self.session = {
            **self.session,
            "status": SessionStatuses.CANCELLED,
            "updated_at": updated_at,
        }
        return self.session

    async def update_session_if_editable(
        self,
        session_id: str,
        *,
        updates: dict[str, object],
        current_time: datetime,
        updated_at: datetime,
    ) -> dict[str, object] | None:
        _ = (current_time,)
        if self.session is None or self.session["id"] != session_id:
            return None
        self.session = {
            **self.session,
            **updates,
            "updated_at": updated_at,
        }
        return self.session


class FakeTicketRepository:
    def __init__(self, ticket: dict[str, object] | None = None) -> None:
        self.ticket = ticket

    async def count_by_session(self, session_id: str, *, active_only: bool = True, db_session=None) -> int:
        _ = (session_id, active_only, db_session)
        return 0

    async def get_by_id(self, ticket_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
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
        current_status: str | None = None,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (updated_at, db_session)
        if self.ticket is None or self.ticket["id"] != ticket_id:
            return None
        if current_status is not None and self.ticket["status"] != current_status:
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


async def fake_run_transaction_with_retry(callback, *, operation_name: str, **_: object):
    _ = operation_name
    return await callback(object())


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


def build_movie(
    movie_id: str = "movie-1",
    *,
    duration_minutes: int = 120,
    poster_url: str | None = None,
    status: str = MovieStatuses.PLANNED,
) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return MovieRead(
        id=movie_id,
        title={"uk": "Інтерстеллар", "en": "Interstellar"},
        description={"uk": "Науково-фантастична драма", "en": "Sci-fi drama"},
        duration_minutes=duration_minutes,
        poster_url=poster_url,
        age_rating="PG-13",
        genres=["science_fiction", "drama"],
        status=status,
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


def test_movie_create_schema_accepts_localized_fields_and_normalizes_genres() -> None:
    payload = MovieCreate(
        title={"uk": "Дюна", "en": "Dune"},
        description={"uk": "Фантастика", "en": "Science fiction"},
        duration_minutes=155,
        genres=["Sci-Fi", " Drama "],
        status=MovieStatuses.PLANNED,
    )

    assert payload.title == LocalizedText(uk="Дюна", en="Dune")
    assert payload.description == LocalizedText(uk="Фантастика", en="Science fiction")
    assert payload.genres == ["science_fiction", "drama"]


def test_movie_update_schema_normalizes_genres_and_keeps_nullables() -> None:
    payload = MovieUpdate(
        title={"en": "New title"},
        genres=[" Drama ", "", "Sci-Fi", "mystery"],
        poster_url=None,
        status=MovieStatuses.DEACTIVATED,
    )

    dumped = payload.model_dump(exclude_unset=True)

    assert dumped["title"] == {"en": "New title"}
    assert dumped["genres"] == ["drama", "science_fiction", "mystery"]
    assert dumped["status"] == MovieStatuses.DEACTIVATED
    assert "poster_url" in dumped
    assert dumped["poster_url"] is None


def test_movie_update_schema_rejects_duplicate_genres_after_normalization() -> None:
    with pytest.raises(ValidationError):
        MovieUpdate(genres=["Drama", " drama "])


def test_movie_create_schema_rejects_invalid_genre_code() -> None:
    with pytest.raises(ValidationError):
        MovieCreate(
            title={"uk": "Тест", "en": "Test"},
            description={"uk": "Опис", "en": "Description"},
            duration_minutes=100,
            genres=["unsupported-genre"],
            status=MovieStatuses.PLANNED,
        )


def test_movie_create_schema_accepts_local_demo_poster_paths_and_blank_age_rating() -> None:
    payload = MovieCreate(
        title={"uk": "Судзуме", "en": "Suzume"},
        description={"uk": "Сучасний аніме-фільм", "en": "Modern anime feature"},
        duration_minutes=122,
        poster_url="/demo-posters/suzume.svg",
        age_rating="   ",
        genres=["animation", "adventure"],
        status=MovieStatuses.PLANNED,
    )

    assert payload.poster_url == "/demo-posters/suzume.svg"
    assert payload.age_rating is None


def test_movie_create_schema_rejects_overlong_localized_title() -> None:
    with pytest.raises(ValidationError):
        MovieCreate(
            title={"uk": "Ж" * 151, "en": "A" * 151},
            description={"uk": "Опис", "en": "Description"},
            duration_minutes=100,
            genres=["drama"],
            status=MovieStatuses.PLANNED,
        )


def test_user_update_requires_current_password_for_sensitive_fields() -> None:
    with pytest.raises(ValueError):
        UserUpdate(email="new@example.com")


def test_user_update_rejects_reusing_current_password() -> None:
    with pytest.raises(ValueError):
        UserUpdate(password="SamePassword123", current_password="SamePassword123")


def test_user_create_rejects_unexpected_role_field() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            name="Escalation Attempt",
            email="escalation@example.com",
            password="CinemaPass123",
            role="admin",
        )


def test_user_update_rejects_unexpected_privilege_fields() -> None:
    with pytest.raises(ValidationError):
        UserUpdate(role="admin")


def test_session_create_rejects_prices_with_more_than_two_decimals() -> None:
    now = datetime.now(tz=timezone.utc)

    with pytest.raises(ValidationError):
        SessionCreate(
            movie_id="movie-1",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            price=199.999,
        )


def test_ticket_read_rejects_cancelled_status_without_cancelled_at() -> None:
    now = datetime.now(tz=timezone.utc)

    with pytest.raises(ValidationError):
        TicketRead(
            id="ticket-1",
            user_id="user-1",
            session_id="session-1",
            seat_row=2,
            seat_number=5,
            price=200.0,
            status=TicketStatuses.CANCELLED,
            purchased_at=now,
            updated_at=None,
            cancelled_at=None,
        )


def test_order_service_build_order_read_serializes_httpurl_poster_url_to_plain_string() -> None:
    poster_url = "https://example.com/posters/interstellar.jpg"
    now = datetime.now(tz=timezone.utc)
    service = OrderService(
        session_repository=FakeSessionRepository(),
        ticket_repository=FakeTicketRepository(),
        movie_repository=FakeMovieRepository(),
        order_repository=FakeOrderRepository(),
    )

    built_order = service._build_order_read(
        order_document={
            "id": "order-1",
            "user_id": "user-1",
            "session_id": "session-1",
            "status": "completed",
            "total_price": 200.0,
            "tickets_count": 1,
            "created_at": now,
            "updated_at": None,
        },
        ticket_documents=[build_ticket()],
        session_document=build_session(),
        movie_document=build_movie(poster_url=poster_url),
        now=now,
    )

    assert built_order.poster_url == poster_url
    assert isinstance(built_order.poster_url, str)


@pytest.mark.asyncio
async def test_admin_service_prevents_deleting_movie_with_sessions() -> None:
    movie_repository = FakeMovieRepository(movie=build_movie())
    session_repository = FakeSessionRepository(count_by_movie=1)
    ticket_repository = FakeTicketRepository()
    service = AdminService(
        movie_repository=movie_repository,
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        order_repository=FakeOrderRepository(),
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
        order_repository=FakeOrderRepository(),
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
async def test_admin_service_rejects_session_slot_with_excessive_runtime_buffer() -> None:
    movie_repository = FakeMovieRepository(movie=build_movie(duration_minutes=120))
    session_repository = FakeSessionRepository()
    ticket_repository = FakeTicketRepository()
    service = AdminService(
        movie_repository=movie_repository,
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        order_repository=FakeOrderRepository(),
    )
    now = datetime.now(tz=timezone.utc) + timedelta(days=1)
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=190)

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
async def test_admin_service_rejects_active_movie_creation_without_sessions() -> None:
    service = AdminService(
        movie_repository=FakeMovieRepository(),
        session_repository=FakeSessionRepository(),
        ticket_repository=FakeTicketRepository(),
        order_repository=FakeOrderRepository(),
    )

    with pytest.raises(ValidationException):
        await service.create_movie(
            MovieCreate(
                title={"uk": "Передчасно активний", "en": "Premature Active"},
                description={"uk": "Має впасти", "en": "Should fail"},
                duration_minutes=90,
                genres=["drama"],
                status=MovieStatuses.ACTIVE,
            ),
            created_by=build_admin_user(),
        )


@pytest.mark.asyncio
async def test_admin_service_promotes_planned_movie_to_active_after_session_creation() -> None:
    movie_repository = FakeMovieRepository(movie=build_movie(status=MovieStatuses.PLANNED))
    session_repository = FakeSessionRepository()
    ticket_repository = FakeTicketRepository()
    service = AdminService(
        movie_repository=movie_repository,
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        order_repository=FakeOrderRepository(),
    )
    now = datetime.now(tz=timezone.utc) + timedelta(days=1)
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=120)

    created = await service.create_session(
        SessionCreate(
            movie_id="movie-1",
            start_time=start_time,
            end_time=end_time,
            price=200,
        ),
        created_by=build_admin_user(),
    )

    assert created.movie.status == MovieStatuses.ACTIVE
    assert movie_repository.movie is not None
    assert movie_repository.movie["status"] == MovieStatuses.ACTIVE


@pytest.mark.asyncio
async def test_ticket_service_cancellation_restores_seat_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.commands.ticket_cancellation.run_transaction_with_retry",
        fake_run_transaction_with_retry,
    )
    session_repository = FakeSessionRepository(session=build_session())
    ticket_repository = FakeTicketRepository(ticket=build_ticket())
    service = TicketService(
        session_repository=session_repository,
        ticket_repository=ticket_repository,
        order_repository=FakeOrderRepository(),
        movie_repository=FakeMovieRepository(movie=build_movie()),
        user_repository=FakeUserRepository(),
    )

    cancelled = await service.cancel_ticket("ticket-1", current_user=build_regular_user())

    assert cancelled.status == TicketStatuses.CANCELLED
    assert cancelled.cancelled_at is not None
    assert session_repository.available_seats == 96
