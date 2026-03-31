"""Schedule service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import NotFoundException
from app.factories.schedule_factory import ScheduleItemFactory, SessionDetailsFactory
from app.repositories.movies import MovieRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.movie import MovieRead
from app.schemas.seat import SeatAvailabilityRead
from app.schemas.session import (
    ScheduleItemRead,
    ScheduleQueryParams,
    SessionDetailsRead,
    SessionRead,
    SessionSeatsRead,
)
from app.strategies.schedule_sorting import ScheduleSortingStrategyFactory
from app.utils.pagination import build_pagination_meta
from app.services.movie_status import MovieStatusManager

logger = get_logger(__name__)


class ScheduleService:
    """Service responsible for schedule browsing use cases."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        movie_repository: MovieRepository,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.movie_repository = movie_repository
        self.movie_status_manager = MovieStatusManager(
            movie_repository=movie_repository,
            session_repository=session_repository,
        )

    async def list_schedule(
        self,
        pagination: PaginationParams,
        filters: ScheduleQueryParams,
    ) -> tuple[list[ScheduleItemRead], PaginationMeta]:
        """Return public schedule items with pagination metadata."""
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        session_documents = await self.session_repository.list_public_schedule(
            current_time=now,
            movie_id=filters.movie_id,
        )
        sessions = [SessionRead.model_validate(document) for document in session_documents]
        movies = await self.movie_repository.list_by_ids([session.movie_id for session in sessions])
        movie_map = {movie["id"]: movie for movie in movies}

        items = [
            ScheduleItemFactory.build(
                session=session,
                movie=self._require_movie(movie_map, session.movie_id),
            )
            for session in sessions
            if session.movie_id in movie_map
        ]
        strategy = ScheduleSortingStrategyFactory.create(
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )
        sorted_items = strategy.sort(items)
        total = len(sorted_items)
        page_items = sorted_items[pagination.offset : pagination.offset + pagination.limit]
        return page_items, build_pagination_meta(pagination, total)

    async def get_session_details(self, session_id: str) -> SessionDetailsRead:
        """Return a session by id or raise if it does not exist."""
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        session_document = await self.session_repository.get_by_id(session_id)
        if session_document is None:
            raise NotFoundException("Session was not found.")

        session = SessionRead.model_validate(session_document)
        movie_document = await self.movie_repository.get_by_id(session.movie_id)
        if movie_document is None:
            raise NotFoundException("Movie for this session was not found.")
        return SessionDetailsFactory.build(
            session=session,
            movie=MovieRead.model_validate(movie_document),
        )

    async def get_session_seats(self, session_id: str) -> SessionSeatsRead:
        """Build seat availability data for a specific session."""
        settings = get_settings()
        session = await self.get_session_details(session_id)
        tickets = await self.ticket_repository.list_by_session(session_id)
        occupied = {
            (ticket["seat_row"], ticket["seat_number"])
            for ticket in tickets
        }
        derived_available_seats = max(session.total_seats - len(occupied), 0)
        if derived_available_seats != session.available_seats:
            logger.warning(
                "Seat counter mismatch detected for session %s: stored=%s derived=%s",
                session.id,
                session.available_seats,
                derived_available_seats,
            )

        seats = [
            SeatAvailabilityRead(
                row=row_index,
                number=seat_index,
                is_available=(row_index, seat_index) not in occupied,
            )
            for row_index in range(1, settings.hall_rows_count + 1)
            for seat_index in range(1, settings.hall_seats_per_row + 1)
        ]
        return SessionSeatsRead(
            session_id=session.id,
            rows_count=settings.hall_rows_count,
            seats_per_row=settings.hall_seats_per_row,
            total_seats=session.total_seats,
            available_seats=derived_available_seats,
            seats=seats,
        )

    def _require_movie(self, movie_map: dict[str, dict], movie_id: str) -> MovieRead:
        movie = movie_map.get(movie_id)
        if movie is None:
            raise NotFoundException("Movie for this session was not found.")
        return MovieRead.model_validate(movie)
