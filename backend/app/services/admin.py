"""Administrative service skeleton."""

from __future__ import annotations

from datetime import datetime, time, timezone
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
from app.schemas.common import DeleteResultRead
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate
from app.schemas.report import AttendanceReportRead, AttendanceSessionSummary
from app.schemas.session import SessionCreate, SessionDetailsRead, SessionRead, SessionUpdate
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

    async def get_movie(self, movie_id: str, requested_by: UserRead) -> MovieRead:
        """Return a movie for administration views."""
        _ = requested_by
        movie = await self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise NotFoundException("Movie was not found.")
        return MovieRead.model_validate(movie)

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
        updates = payload.model_dump(mode="python", exclude_unset=True)
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

    async def deactivate_movie(self, movie_id: str, deactivated_by: UserRead) -> MovieRead:
        """Soft-disable a movie while keeping existing sessions and tickets intact."""
        _ = deactivated_by
        movie = await self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise NotFoundException("Movie was not found.")
        if movie.get("is_active") is False:
            return MovieRead.model_validate(movie)

        updated = await self.movie_repository.update_movie(
            movie_id=movie_id,
            updates={"is_active": False},
            updated_at=datetime.now(tz=timezone.utc),
        )
        if updated is None:
            raise NotFoundException("Movie was not found.")
        return MovieRead.model_validate(updated)

    async def delete_movie(self, movie_id: str, deleted_by: UserRead) -> DeleteResultRead:
        """Delete a movie only when no sessions reference it.

        We keep movie deletion conservative because session and ticket history should not lose
        their source movie record. If a movie has ever been scheduled, admins should deactivate it.
        """
        _ = deleted_by
        movie = await self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise NotFoundException("Movie was not found.")

        linked_sessions = await self.session_repository.count_by_movie(movie_id)
        if linked_sessions > 0:
            raise ConflictException("Movies used in sessions cannot be deleted. Deactivate the movie instead.")

        deleted = await self.movie_repository.delete_movie(movie_id)
        if not deleted:
            raise NotFoundException("Movie was not found.")
        return DeleteResultRead(id=movie_id)

    async def list_sessions(self, requested_by: UserRead) -> list[SessionDetailsRead]:
        """Return all sessions with attached movie data for the admin board."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        sessions = [SessionRead.model_validate(document) for document in await self.session_repository.list_all()]
        movies = await self.movie_repository.list_by_ids([session.movie_id for session in sessions])
        movie_map = {movie["id"]: MovieRead.model_validate(movie) for movie in movies}
        return [
            SessionDetailsFactory.build(session=session, movie=movie_map[session.movie_id])
            for session in sessions
            if session.movie_id in movie_map
        ]

    async def get_session(self, session_id: str, requested_by: UserRead) -> SessionDetailsRead:
        """Return a single session with movie details for the admin board."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        session_document = await self.session_repository.get_by_id(session_id)
        if session_document is None:
            raise NotFoundException("Session was not found.")

        movie_document = await self.movie_repository.get_by_id(session_document["movie_id"])
        if movie_document is None:
            raise NotFoundException("Movie for this session was not found.")

        return SessionDetailsFactory.build(
            session=SessionRead.model_validate(session_document),
            movie=MovieRead.model_validate(movie_document),
        )

    async def create_session(self, payload: SessionCreate, created_by: UserRead) -> SessionDetailsRead:
        """Create a new session slot for an existing movie."""
        _ = created_by
        settings = get_settings()
        now = datetime.now(tz=timezone.utc)

        start_time = self._normalize_session_time(payload.start_time)
        end_time = self._normalize_session_time(payload.end_time)
        movie = await self._require_movie_for_scheduling(payload.movie_id)
        self._validate_session_slot(movie=movie, start_time=start_time, end_time=end_time, now=now)

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

    async def update_session(
        self,
        session_id: str,
        payload: SessionUpdate,
        updated_by: UserRead,
    ) -> SessionDetailsRead:
        """Update a scheduled session that does not already have purchased tickets."""
        _ = updated_by
        updates = payload.model_dump(mode="python", exclude_none=True)
        if not updates:
            raise ValidationException("At least one session field must be provided for update.")

        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        existing_session = await self.session_repository.get_by_id(session_id)
        if existing_session is None:
            raise NotFoundException("Session was not found.")
        if existing_session["status"] != SessionStatuses.SCHEDULED:
            raise ConflictException("Only scheduled sessions can be edited.")

        purchased_tickets = await self.ticket_repository.count_by_session(session_id, active_only=True)
        if purchased_tickets > 0:
            raise ConflictException("Sessions with purchased tickets cannot be edited. Cancel the session instead.")

        movie_id = str(updates.get("movie_id", existing_session["movie_id"]))
        start_time = self._normalize_session_time(
            updates["start_time"] if "start_time" in updates else existing_session["start_time"]
        )
        end_time = self._normalize_session_time(
            updates["end_time"] if "end_time" in updates else existing_session["end_time"]
        )

        movie = await self._require_movie_for_scheduling(
            movie_id,
            allow_inactive_when_same=movie_id == existing_session["movie_id"],
        )
        self._validate_session_slot(movie=movie, start_time=start_time, end_time=end_time, now=now)

        overlapping = await self.session_repository.find_overlapping(
            start_time=start_time,
            end_time=end_time,
            exclude_session_id=session_id,
        )
        if overlapping is not None:
            raise ConflictException("Session overlaps with an existing session in the only hall.")

        updated_document = await self.session_repository.update_session(
            session_id,
            updates={
                "movie_id": movie_id,
                "start_time": start_time,
                "end_time": end_time,
                "price": updates.get("price", existing_session["price"]),
            },
            updated_at=now,
        )
        if updated_document is None:
            raise NotFoundException("Session was not found.")

        return SessionDetailsFactory.build(
            session=SessionRead.model_validate(updated_document),
            movie=movie,
        )

    async def delete_session(self, session_id: str, deleted_by: UserRead) -> DeleteResultRead:
        """Delete a session only when no tickets have ever been stored for it."""
        _ = deleted_by
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            raise NotFoundException("Session was not found.")

        stored_tickets = await self.ticket_repository.count_by_session(session_id, active_only=False)
        if stored_tickets > 0:
            raise ConflictException("Sessions with stored tickets cannot be deleted. Cancel the session instead.")

        deleted = await self.session_repository.delete_session(session_id)
        if not deleted:
            raise NotFoundException("Session was not found.")
        return DeleteResultRead(id=session_id)

    async def build_attendance_report(self, requested_by: UserRead) -> AttendanceReportRead:
        """Build an attendance report across all sessions."""
        _ = requested_by
        builder = AttendanceReportBuilder()
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        sessions = [SessionRead.model_validate(document) for document in await self.session_repository.list_all()]
        movies = await self.movie_repository.list_by_ids([session.movie_id for session in sessions])
        movie_map = {movie["id"]: MovieRead.model_validate(movie) for movie in movies}

        for session in sessions:
            movie = movie_map.get(session.movie_id)
            if movie is None:
                continue
            tickets_sold = await self.ticket_repository.count_by_session(session.id, active_only=True)
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

    async def _require_movie_for_scheduling(
        self,
        movie_id: str,
        *,
        allow_inactive_when_same: bool = False,
    ) -> MovieRead:
        movie_document = await self.movie_repository.get_by_id(movie_id)
        if movie_document is None:
            raise NotFoundException("Movie was not found.")
        movie = MovieRead.model_validate(movie_document)
        if not movie.is_active and not allow_inactive_when_same:
            raise ValidationException("Inactive movies cannot be scheduled.")
        return movie

    def _validate_session_slot(
        self,
        *,
        movie: MovieRead,
        start_time: datetime,
        end_time: datetime,
        now: datetime,
    ) -> None:
        if start_time <= now:
            raise ValidationException("Session start time must be in the future.")
        self._validate_start_time(start_time)
        if end_time <= start_time:
            raise ValidationException("Session end time must be greater than start time.")
        minimum_duration_minutes = (end_time - start_time).total_seconds() / 60
        if minimum_duration_minutes < movie.duration_minutes:
            raise ValidationException("Session slot must be at least as long as the selected movie duration.")
