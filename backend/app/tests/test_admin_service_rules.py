"""Focused admin service tests for rule-heavy edge cases."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.constants import MovieStatuses, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.schemas.movie import MovieUpdate
from app.schemas.session import SessionBatchCreate, SessionUpdate
from app.services.admin import AdminService
from app.tests.test_management_services import (
    FakeOrderRepository,
    FakeTicketRepository,
    build_admin_user,
    build_movie,
    build_session,
    build_ticket,
)


class FakeMovieStatusManager:
    def __init__(self, *, has_future_sessions: bool = False) -> None:
        self.has_future_sessions_value = has_future_sessions
        self.refresh_calls: list[datetime] = []

    async def refresh_statuses(self, *, current_time: datetime) -> None:
        self.refresh_calls.append(current_time)

    async def has_future_sessions(self, movie_id: str, *, current_time: datetime) -> bool:
        _ = (movie_id, current_time)
        return self.has_future_sessions_value


class AdminMovieRepository:
    def __init__(
        self,
        movie: dict[str, object] | None = None,
        *,
        update_returns_none: bool = False,
        delete_returns: bool = True,
    ) -> None:
        self.movie = movie
        self.update_returns_none = update_returns_none
        self.delete_returns = delete_returns
        self.update_calls: list[dict[str, object]] = []

    async def get_by_id(self, movie_id: str) -> dict[str, object] | None:
        if self.movie is None or self.movie["id"] != movie_id:
            return None
        return dict(self.movie)

    async def list_movies(self, *, active_only: bool) -> list[dict[str, object]]:
        _ = active_only
        return [dict(self.movie)] if self.movie is not None else []

    async def list_by_ids(self, movie_ids: list[str]) -> list[dict[str, object]]:
        if self.movie is None or self.movie["id"] not in movie_ids:
            return []
        return [dict(self.movie)]

    async def update_movie(
        self,
        movie_id: str,
        updates: dict[str, object],
        updated_at: datetime,
    ) -> dict[str, object] | None:
        self.update_calls.append(
            {
                "movie_id": movie_id,
                "updates": updates,
                "updated_at": updated_at,
            }
        )
        if self.movie is None or self.movie["id"] != movie_id or self.update_returns_none:
            return None
        self.movie = {**self.movie, **updates, "updated_at": updated_at}
        return dict(self.movie)

    async def create_movie(self, document: dict[str, object]) -> dict[str, object]:
        self.movie = {**document, "id": "movie-1"}
        return dict(self.movie)

    async def delete_movie(self, movie_id: str) -> bool:
        if self.movie is None or self.movie["id"] != movie_id:
            return False
        if not self.delete_returns:
            return False
        self.movie = None
        return True


class AdminSessionRepository:
    def __init__(
        self,
        session: dict[str, object] | None = None,
        *,
        count_by_movie: int = 0,
        overlapping: dict[str, object] | None = None,
        update_returns_none: bool = False,
        delete_returns: bool = True,
    ) -> None:
        self.session = session
        self.count_by_movie_value = count_by_movie
        self.overlapping = overlapping
        self.update_returns_none = update_returns_none
        self.delete_returns = delete_returns
        self.deleted_session_id: str | None = None

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime) -> int:
        _ = (current_time, updated_at)
        return 0

    async def list_movie_ids_with_future_scheduled_sessions(self, *, current_time: datetime) -> list[str]:
        if (
            self.session is not None
            and self.session["status"] == SessionStatuses.SCHEDULED
            and self.session["start_time"] > current_time
        ):
            return [str(self.session["movie_id"])]
        return []

    async def has_future_scheduled_sessions(self, movie_id: str, *, current_time: datetime) -> bool:
        return (
            self.session is not None
            and self.session["movie_id"] == movie_id
            and self.session["status"] == SessionStatuses.SCHEDULED
            and self.session["start_time"] > current_time
        )

    async def count_by_movie(self, movie_id: str) -> int:
        _ = movie_id
        return self.count_by_movie_value

    async def list_all(self) -> list[dict[str, object]]:
        return [dict(self.session)] if self.session is not None else []

    async def get_by_id(self, session_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
        if self.session is None or self.session["id"] != session_id:
            return None
        return dict(self.session)

    async def find_overlapping(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        exclude_session_id: str | None = None,
    ) -> dict[str, object] | None:
        _ = (start_time, end_time, exclude_session_id)
        return self.overlapping

    async def create_session(self, document: dict[str, object]) -> dict[str, object]:
        self.session = {**document, "id": "session-1"}
        return dict(self.session)

    async def update_session_if_editable(
        self,
        session_id: str,
        *,
        updates: dict[str, object],
        current_time: datetime,
        updated_at: datetime,
    ) -> dict[str, object] | None:
        _ = current_time
        if self.session is None or self.session["id"] != session_id or self.update_returns_none:
            return None
        self.session = {**self.session, **updates, "updated_at": updated_at}
        return dict(self.session)

    async def delete_session(self, session_id: str, *, db_session=None) -> bool:
        _ = db_session
        self.deleted_session_id = session_id
        if self.session is None or self.session["id"] != session_id:
            return False
        if not self.delete_returns:
            return False
        self.session = None
        return True


def build_service(
    *,
    movie: dict[str, object] | None = None,
    session: dict[str, object] | None = None,
    tickets: list[dict[str, object]] | None = None,
    movie_repository: AdminMovieRepository | None = None,
    session_repository: AdminSessionRepository | None = None,
    has_future_sessions: bool = False,
) -> AdminService:
    service = AdminService(
        movie_repository=movie_repository or AdminMovieRepository(movie),
        session_repository=session_repository or AdminSessionRepository(session),
        ticket_repository=FakeTicketRepository(tickets=tickets or []),
        order_repository=FakeOrderRepository(),
    )
    service.movie_status_manager = FakeMovieStatusManager(has_future_sessions=has_future_sessions)
    return service


async def run_without_real_transaction(callback, *, operation_name: str, **_: object):
    assert operation_name == "delete_session"
    return await callback(object())


def future_window(*, days: int = 1, hour: int = 10, minutes: int = 120) -> tuple[datetime, datetime]:
    start = (datetime.now(tz=timezone.utc) + timedelta(days=days)).replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start, start + timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_update_movie_reports_missing_movie() -> None:
    service = build_service()

    with pytest.raises(NotFoundException, match="Movie was not found."):
        await service.update_movie("missing", MovieUpdate(status=MovieStatuses.DEACTIVATED), updated_by=build_admin_user())


@pytest.mark.asyncio
async def test_update_movie_rejects_noop_payload() -> None:
    service = build_service(movie=build_movie())

    with pytest.raises(ValidationException, match="At least one movie field"):
        await service.update_movie("movie-1", MovieUpdate(), updated_by=build_admin_user())


@pytest.mark.asyncio
async def test_update_movie_reports_stale_update_race() -> None:
    service = build_service(
        movie_repository=AdminMovieRepository(build_movie(), update_returns_none=True),
    )

    with pytest.raises(NotFoundException, match="Movie was not found."):
        await service.update_movie(
            "movie-1",
            MovieUpdate(status=MovieStatuses.DEACTIVATED),
            updated_by=build_admin_user(),
        )


@pytest.mark.asyncio
async def test_update_movie_refreshes_statuses_after_demoting_active_movie() -> None:
    service = build_service(movie=build_movie(status=MovieStatuses.ACTIVE))

    updated = await service.update_movie(
        "movie-1",
        MovieUpdate(status=MovieStatuses.DEACTIVATED),
        updated_by=build_admin_user(),
    )

    assert updated.status == MovieStatuses.DEACTIVATED
    assert len(service.movie_status_manager.refresh_calls) == 2


@pytest.mark.asyncio
async def test_deactivate_movie_returns_existing_deactivated_movie_without_update() -> None:
    movie_repository = AdminMovieRepository(build_movie(status=MovieStatuses.DEACTIVATED))
    service = build_service(movie_repository=movie_repository)

    movie = await service.deactivate_movie("movie-1", deactivated_by=build_admin_user())

    assert movie.status == MovieStatuses.DEACTIVATED
    assert movie_repository.update_calls == []


@pytest.mark.asyncio
async def test_deactivate_movie_reports_stale_update_race() -> None:
    service = build_service(
        movie_repository=AdminMovieRepository(build_movie(), update_returns_none=True),
    )

    with pytest.raises(NotFoundException, match="Movie was not found."):
        await service.deactivate_movie("movie-1", deactivated_by=build_admin_user())


@pytest.mark.parametrize(
    ("movie", "delete_returns", "expected_message"),
    [
        (None, True, "Movie was not found."),
        (build_movie(), False, "Movie was not found."),
    ],
)
@pytest.mark.asyncio
async def test_delete_movie_reports_missing_or_stale_delete(
    movie: dict[str, object] | None,
    delete_returns: bool,
    expected_message: str,
) -> None:
    service = build_service(
        movie_repository=AdminMovieRepository(movie, delete_returns=delete_returns),
    )

    with pytest.raises(NotFoundException, match=expected_message):
        await service.delete_movie("movie-1", deleted_by=build_admin_user())


@pytest.mark.asyncio
async def test_get_session_reports_missing_session() -> None:
    service = build_service(movie=build_movie())

    with pytest.raises(NotFoundException, match="Session was not found."):
        await service.get_session("session-1", requested_by=build_admin_user())


@pytest.mark.asyncio
async def test_get_session_reports_missing_movie_for_existing_session() -> None:
    service = build_service(session=build_session())

    with pytest.raises(NotFoundException, match="Movie for this session was not found."):
        await service.get_session("session-1", requested_by=build_admin_user())


@pytest.mark.asyncio
async def test_create_sessions_batch_returns_rejections_without_refreshing_created_sessions() -> None:
    service = build_service(movie=build_movie())
    template_start = datetime(2000, 1, 1, 10, tzinfo=timezone.utc)

    result = await service.create_sessions_batch(
        SessionBatchCreate(
            movie_id="movie-1",
            start_time=template_start,
            end_time=template_start + timedelta(minutes=120),
            price=200,
            dates=[date(2000, 1, 1)],
        ),
        created_by=build_admin_user(),
    )

    assert result.created_count == 0
    assert result.rejected_count == 1
    assert result.rejected_dates[0].message == "Session start time must be in the future."
    assert len(service.movie_status_manager.refresh_calls) == 1


@pytest.mark.asyncio
async def test_update_session_rejects_empty_payload_and_missing_session() -> None:
    service = build_service(movie=build_movie())

    with pytest.raises(ValidationException, match="At least one session field"):
        await service.update_session("session-1", SessionUpdate(), updated_by=build_admin_user())

    with pytest.raises(NotFoundException, match="Session was not found."):
        await service.update_session("session-1", SessionUpdate(price=240), updated_by=build_admin_user())


@pytest.mark.asyncio
async def test_update_session_rejects_sessions_with_purchased_tickets() -> None:
    session = {**build_session(), "available_seats": 96}
    service = build_service(
        movie=build_movie(),
        session=session,
        tickets=[build_ticket(session_id="session-1", status=TicketStatuses.PURCHASED)],
    )

    with pytest.raises(ConflictException, match="purchased tickets cannot be edited"):
        await service.update_session("session-1", SessionUpdate(price=240), updated_by=build_admin_user())


@pytest.mark.asyncio
async def test_update_session_applies_valid_changes_and_returns_movie_details() -> None:
    start_time, end_time = future_window(hour=12)
    service = build_service(
        movie=build_movie(),
        session={**build_session(start_time=start_time), "available_seats": 96},
    )

    updated = await service.update_session(
        "session-1",
        SessionUpdate(start_time=start_time, end_time=end_time, price=255),
        updated_by=build_admin_user(),
    )

    assert updated.id == "session-1"
    assert updated.price == 255
    assert updated.movie.id == "movie-1"


@pytest.mark.parametrize(
    ("session_updates", "expected_message"),
    [
        ({"status": SessionStatuses.CANCELLED}, "Cancelled sessions cannot be edited."),
        ({"status": SessionStatuses.COMPLETED}, "Completed sessions cannot be edited."),
        ({"status": "maintenance"}, "Only scheduled sessions can be edited."),
        ({"start_time": datetime.now(tz=timezone.utc) - timedelta(minutes=1)}, "Only future scheduled sessions"),
        ({"available_seats": 95, "total_seats": 96}, "purchased tickets cannot be edited"),
    ],
)
def test_get_session_update_blocker_explains_non_editable_states(
    session_updates: dict[str, object],
    expected_message: str,
) -> None:
    service = build_service()
    session = {**build_session(), **session_updates}

    assert expected_message in service._get_session_update_blocker(session, now=datetime.now(tz=timezone.utc))


@pytest.mark.asyncio
async def test_validate_requested_movie_status_rejects_manual_active_without_future_sessions() -> None:
    service = build_service(has_future_sessions=False)

    with pytest.raises(ValidationException, match="become active automatically"):
        await service._validate_requested_movie_status(
            movie_id="movie-1",
            requested_status=MovieStatuses.ACTIVE,
            current_time=datetime.now(tz=timezone.utc),
        )


@pytest.mark.asyncio
async def test_validate_requested_movie_status_rejects_demoting_movie_with_future_sessions() -> None:
    service = build_service(has_future_sessions=True)

    with pytest.raises(ConflictException, match="future scheduled sessions stay active"):
        await service._validate_requested_movie_status(
            movie_id="movie-1",
            requested_status=MovieStatuses.DEACTIVATED,
            current_time=datetime.now(tz=timezone.utc),
        )


@pytest.mark.asyncio
async def test_delete_session_removes_ticketless_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.admin.run_transaction_with_retry", run_without_real_transaction)
    session_repository = AdminSessionRepository(build_session())
    service = build_service(movie=build_movie(), session_repository=session_repository)

    result = await service.delete_session("session-1", deleted_by=build_admin_user())

    assert result.id == "session-1"
    assert session_repository.deleted_session_id == "session-1"
    assert session_repository.session is None


@pytest.mark.parametrize(
    ("session", "tickets", "delete_returns", "expected_exception", "expected_message"),
    [
        (None, [], True, NotFoundException, "Session was not found."),
        (build_session(), [build_ticket(session_id="session-1")], True, ConflictException, "stored tickets cannot be deleted"),
        (build_session(), [], False, NotFoundException, "Session was not found."),
    ],
)
@pytest.mark.asyncio
async def test_delete_session_rejects_missing_ticketed_or_stale_sessions(
    monkeypatch: pytest.MonkeyPatch,
    session: dict[str, object] | None,
    tickets: list[dict[str, object]],
    delete_returns: bool,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    monkeypatch.setattr("app.services.admin.run_transaction_with_retry", run_without_real_transaction)
    service = build_service(
        movie=build_movie(),
        session_repository=AdminSessionRepository(session, delete_returns=delete_returns),
        tickets=tickets,
    )

    with pytest.raises(expected_exception, match=expected_message):
        await service.delete_session("session-1", deleted_by=build_admin_user())
