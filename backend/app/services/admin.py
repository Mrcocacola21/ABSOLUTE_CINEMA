"""Administrative service skeleton."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.builders.attendance_report import AttendanceReportBuilder
from app.commands.session_cancellation import SessionCancellationCommand
from app.core.config import get_settings
from app.core.constants import SessionStatuses
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.factories.schedule_factory import SessionDetailsFactory
from app.observers.events import build_default_event_publisher
from app.repositories.movies import MovieRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate
from app.schemas.report import AttendanceReportRead, AttendanceSessionSummary
from app.schemas.session import SessionCreate, SessionDetailsRead, SessionRead
from app.schemas.user import UserRead


class AdminService:
    """Service for administration use cases."""

    def __init__(
        self,
        movie_repository: MovieRepository,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
    ) -> None:
        self.movie_repository = movie_repository
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.event_publisher = build_default_event_publisher()

    async def list_movies(self, requested_by: UserRead) -> list[MovieRead]:
        """Return all movies for administration views."""
        _ = requested_by
        movies = await self.movie_repository.list_movies(active_only=False)
        return [MovieRead.model_validate(movie) for movie in movies]

    async def create_movie(self, payload: MovieCreate, created_by: UserRead) -> MovieRead:
        """Create a new movie available for future scheduling."""
        _ = created_by
        now = datetime.now(tz=timezone.utc)
        document = payload.model_dump(mode="python")
        document["created_at"] = now
        document["updated_at"] = None
        movie = await self.movie_repository.create_movie(document)
        return MovieRead.model_validate(movie)

    async def update_movie(
        self,
        movie_id: str,
        payload: MovieUpdate,
        updated_by: UserRead,
    ) -> MovieRead:
        """Update editable movie information."""
        _ = updated_by
        updates = payload.model_dump(mode="python", exclude_none=True)
        if not updates:
            raise ValidationException("At least one movie field must be provided for update.")

        updated = await self.movie_repository.update_movie(
            movie_id=movie_id,
            updates=updates,
            updated_at=datetime.now(tz=timezone.utc),
        )
        if updated is None:
            raise NotFoundException("Movie was not found.")
        return MovieRead.model_validate(updated)

    async def list_sessions(self, requested_by: UserRead) -> list[SessionDetailsRead]:
        """Return all sessions with attached movie data for the admin board."""
        _ = requested_by
        sessions = [SessionRead.model_validate(document) for document in await self.session_repository.list_all()]
        movies = await self.movie_repository.list_by_ids([session.movie_id for session in sessions])
        movie_map = {movie["id"]: MovieRead.model_validate(movie) for movie in movies}
        return [
            SessionDetailsFactory.build(session=session, movie=movie_map[session.movie_id])
            for session in sessions
            if session.movie_id in movie_map
        ]

    async def create_session(self, payload: SessionCreate, created_by: UserRead) -> SessionDetailsRead:
        """Create a new session slot for an existing movie."""
        _ = created_by
        settings = get_settings()
        now = datetime.now(tz=timezone.utc)

        movie_document = await self.movie_repository.get_by_id(payload.movie_id)
        if movie_document is None:
            raise NotFoundException("Movie was not found.")
        movie = MovieRead.model_validate(movie_document)
        if not movie.is_active:
            raise ValidationException("Inactive movies cannot be scheduled.")

        start_time = self._normalize_session_time(payload.start_time)
        if start_time <= now:
            raise ValidationException("Session start time must be in the future.")
        self._validate_start_time(start_time)
        end_time = start_time + timedelta(minutes=movie.duration_minutes)
        if end_time <= start_time:
            raise ValidationException("Session end time must be greater than start time.")

        overlapping = await self.session_repository.find_overlapping(
            start_time=start_time,
            end_time=end_time,
        )
        if overlapping is not None:
            raise ConflictException("Session overlaps with an existing session in the only hall.")

        document = {
            "movie_id": payload.movie_id,
            "start_time": start_time,
            "end_time": end_time,
            "price": payload.price,
            "status": SessionStatuses.SCHEDULED,
            "total_seats": settings.total_seats,
            "available_seats": settings.total_seats,
            "created_at": now,
            "updated_at": None,
        }

        session_document = await self.session_repository.create_session(document)
        session = SessionRead.model_validate(session_document)
        return SessionDetailsFactory.build(session=session, movie=movie)

    async def cancel_session(self, session_id: str, cancelled_by: UserRead) -> SessionRead:
        """Cancel an existing session via a command object."""
        command = SessionCancellationCommand(
            session_repository=self.session_repository,
            event_publisher=self.event_publisher,
        )
        return await command.execute(session_id=session_id, cancelled_by=cancelled_by)

    async def build_attendance_report(self, requested_by: UserRead) -> AttendanceReportRead:
        """Build an attendance report across all sessions."""
        _ = requested_by
        builder = AttendanceReportBuilder()
        sessions = [SessionRead.model_validate(document) for document in await self.session_repository.list_all()]
        movies = await self.movie_repository.list_by_ids([session.movie_id for session in sessions])
        movie_map = {movie["id"]: MovieRead.model_validate(movie) for movie in movies}

        for session in sessions:
            movie = movie_map.get(session.movie_id)
            if movie is None:
                continue
            tickets_sold = await self.ticket_repository.count_by_session(session.id)
            summary = AttendanceSessionSummary(
                session_id=session.id,
                movie_title=movie.title,
                start_time=session.start_time,
                status=session.status,
                tickets_sold=tickets_sold,
                total_seats=session.total_seats,
                available_seats=session.available_seats,
                attendance_rate=(tickets_sold / session.total_seats) if session.total_seats else 0,
            )
            builder.add_session(summary)
        return builder.build()

    def _validate_start_time(self, start_time: datetime) -> None:
        settings = get_settings()
        earliest = time(hour=settings.first_session_hour, minute=0)
        latest = time(hour=settings.last_session_start_hour, minute=0)
        local_start_time = start_time.astimezone(ZoneInfo(settings.cinema_timezone))
        candidate = local_start_time.timetz().replace(tzinfo=None)
        if candidate < earliest or candidate > latest:
            raise ValidationException("Session start time must be between 09:00 and 22:00.")

    def _normalize_session_time(self, start_time: datetime) -> datetime:
        settings = get_settings()
        cinema_timezone = ZoneInfo(settings.cinema_timezone)
        if start_time.tzinfo is None:
            return start_time.replace(tzinfo=cinema_timezone).astimezone(timezone.utc)
        return start_time.astimezone(timezone.utc)
