"""Administrative service skeleton."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.builders.attendance_report import AttendanceReportBuilder
from app.commands.session_cancellation import SessionCancellationCommand
from app.core.config import get_settings
from app.core.constants import MovieStatuses, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.db.transactions import run_transaction_with_retry
from app.factories.schedule_factory import SessionDetailsFactory
from app.observers.events import build_default_event_publisher
from app.repositories.movies import MovieRepository
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.schemas.common import DeleteResultRead
from app.schemas.movie import (
    MovieCreate,
    MovieRead,
    MovieUpdate,
    build_movie_normalization_updates,
    merge_movie_localized_updates,
)
from app.schemas.report import (
    AttendanceReportRead,
    AttendanceSessionDetailsRead,
    AttendanceSessionSummary,
    AttendanceTicketDetailsRead,
)
from app.schemas.seat import SeatAvailabilityRead
from app.schemas.session import (
    SessionBatchCreate,
    SessionBatchCreateRead,
    SessionBatchRejectedDateRead,
    SessionCreate,
    SessionDetailsRead,
    SessionRead,
    SessionSeatsRead,
    SessionUpdate,
)
from app.schemas.user import UserRead
from app.services.movie_status import MovieStatusManager

MAX_SESSION_RUNTIME_BUFFER_MINUTES = 60


class AdminService:
    """Service for administration use cases."""

    def __init__(
        self,
        movie_repository: MovieRepository,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        order_repository: OrderRepository,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.movie_repository = movie_repository
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.order_repository = order_repository
        self.user_repository = user_repository or UserRepository()
        self.event_publisher = build_default_event_publisher()
        self.movie_status_manager = MovieStatusManager(
            movie_repository=movie_repository,
            session_repository=session_repository,
        )

    async def list_movies(self, requested_by: UserRead) -> list[MovieRead]:
        """Return all movies for administration views."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        movies = await self.movie_repository.list_movies(active_only=False)
        return sorted(
            (MovieRead.model_validate(movie) for movie in movies),
            key=lambda movie: movie.title.resolve("uk").casefold(),
        )

    async def get_movie(self, movie_id: str, requested_by: UserRead) -> MovieRead:
        """Return a movie for administration views."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        return await self._get_movie_or_not_found(movie_id)

    async def create_movie(self, payload: MovieCreate, created_by: UserRead) -> MovieRead:
        """Create a new movie available for future scheduling."""
        _ = created_by
        if payload.status == MovieStatuses.ACTIVE:
            raise ValidationException(
                "New movies must start as planned or deactivated. Active status is assigned automatically after scheduling."
            )
        now = datetime.now(tz=timezone.utc)
        document = self._normalize_movie_document(payload.model_dump(mode="python"))
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
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        movie_document = await self.movie_repository.get_by_id(movie_id)
        if movie_document is None:
            raise NotFoundException("Movie was not found.")
        movie = MovieRead.model_validate(movie_document)
        updates = merge_movie_localized_updates(
            movie,
            self._normalize_movie_document(payload.model_dump(mode="python", exclude_unset=True)),
        )
        updates = {
            **build_movie_normalization_updates(movie_document, movie),
            **updates,
        }
        if not updates:
            raise ValidationException("At least one movie field must be provided for update.")

        if "status" in updates:
            await self._validate_requested_movie_status(
                movie_id=movie_id,
                requested_status=str(updates["status"]),
                current_time=now,
            )

        updated = await self.movie_repository.update_movie(
            movie_id=movie_id,
            updates=updates,
            updated_at=now,
        )
        if updated is None:
            raise NotFoundException("Movie was not found.")
        if "status" in updates and movie.status == MovieStatuses.ACTIVE and updates["status"] != MovieStatuses.ACTIVE:
            await self.movie_status_manager.refresh_statuses(current_time=now)
        return MovieRead.model_validate(updated)

    async def deactivate_movie(self, movie_id: str, deactivated_by: UserRead) -> MovieRead:
        """Soft-disable a movie while keeping existing sessions and tickets intact."""
        _ = deactivated_by
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        movie = await self._get_movie_or_not_found(movie_id)
        if await self.movie_status_manager.has_future_sessions(movie_id, current_time=now):
            raise ConflictException(
                "Movies with future scheduled sessions cannot be deactivated. Cancel or move those sessions first."
            )
        if movie.status == MovieStatuses.DEACTIVATED:
            return movie

        updated = await self.movie_repository.update_movie(
            movie_id=movie_id,
            updates={"status": MovieStatuses.DEACTIVATED},
            updated_at=now,
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
        await self.movie_status_manager.refresh_statuses(current_time=now)
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
        await self.movie_status_manager.refresh_statuses(current_time=now)
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
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)

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

        session_document = await self.session_repository.create_session(
            self._build_session_document(
                movie_id=payload.movie_id,
                start_time=start_time,
                end_time=end_time,
                price=payload.price,
                created_at=now,
            )
        )
        await self.movie_status_manager.refresh_statuses(current_time=now)
        session = SessionRead.model_validate(session_document)
        return SessionDetailsFactory.build(
            session=session,
            movie=await self._get_movie_or_not_found(payload.movie_id),
        )

    async def create_sessions_batch(
        self,
        payload: SessionBatchCreate,
        created_by: UserRead,
    ) -> SessionBatchCreateRead:
        """Create the same movie slot across multiple selected dates.

        The operation is intentionally partial-success friendly for admin planning flows:
        each requested date is validated independently and conflicting dates are returned
        in the response instead of aborting the whole batch.
        """
        _ = created_by
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)

        movie = await self._require_movie_for_scheduling(payload.movie_id)
        template_start_time = self._normalize_session_time(payload.start_time)
        template_end_time = self._normalize_session_time(payload.end_time)
        self._validate_session_window(movie=movie, start_time=template_start_time, end_time=template_end_time)

        created_documents: list[dict[str, object]] = []
        rejected_dates: list[SessionBatchRejectedDateRead] = []

        for requested_date in payload.dates:
            start_time, end_time = self._build_session_window_for_date(
                template_start_time=template_start_time,
                template_end_time=template_end_time,
                target_date=requested_date,
            )

            try:
                self._validate_session_slot(movie=movie, start_time=start_time, end_time=end_time, now=now)
            except ValidationException as exc:
                rejected_dates.append(
                    SessionBatchRejectedDateRead(
                        date=requested_date,
                        start_time=start_time,
                        end_time=end_time,
                        code=exc.code,
                        message=exc.message,
                    )
                )
                continue

            overlapping = await self.session_repository.find_overlapping(
                start_time=start_time,
                end_time=end_time,
            )
            if overlapping is not None:
                rejected_dates.append(
                    SessionBatchRejectedDateRead(
                        date=requested_date,
                        start_time=start_time,
                        end_time=end_time,
                        code="conflict",
                        message="Session overlaps with an existing session in the only hall.",
                        blocking_session_id=str(overlapping["id"]),
                    )
                )
                continue

            created_documents.append(
                await self.session_repository.create_session(
                    self._build_session_document(
                        movie_id=payload.movie_id,
                        start_time=start_time,
                        end_time=end_time,
                        price=payload.price,
                        created_at=now,
                    )
                )
            )

        if created_documents:
            await self.movie_status_manager.refresh_statuses(current_time=now)

        scheduled_movie = await self._get_movie_or_not_found(payload.movie_id)
        created_sessions = [
            SessionDetailsFactory.build(
                session=SessionRead.model_validate(document),
                movie=scheduled_movie,
            )
            for document in created_documents
        ]

        return SessionBatchCreateRead(
            requested_dates=payload.dates,
            requested_count=len(payload.dates),
            created_count=len(created_sessions),
            rejected_count=len(rejected_dates),
            created_sessions=created_sessions,
            rejected_dates=rejected_dates,
        )

    async def cancel_session(self, session_id: str, cancelled_by: UserRead) -> SessionRead:
        """Cancel an existing session via a command object."""
        command = SessionCancellationCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
            event_publisher=self.event_publisher,
        )
        cancelled_session = await command.execute(session_id=session_id, cancelled_by=cancelled_by)
        await self.movie_status_manager.refresh_statuses(current_time=datetime.now(tz=timezone.utc))
        return cancelled_session

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
        await self.movie_status_manager.refresh_statuses(current_time=now)

        existing_session = await self.session_repository.get_by_id(session_id)
        if existing_session is None:
            raise NotFoundException("Session was not found.")
        update_blocker = self._get_session_update_blocker(existing_session, now=now)
        if update_blocker is not None:
            raise ConflictException(update_blocker)

        purchased_tickets = await self.ticket_repository.count_by_session(session_id, active_only=True)
        if purchased_tickets > 0:
            raise ConflictException(
                "Sessions with purchased tickets cannot be edited. Cancel the session instead."
            )

        movie_id = str(updates.get("movie_id", existing_session["movie_id"]))
        start_time = self._normalize_session_time(
            updates["start_time"] if "start_time" in updates else existing_session["start_time"]
        )
        end_time = self._normalize_session_time(
            updates["end_time"] if "end_time" in updates else existing_session["end_time"]
        )

        movie = await self._require_movie_for_scheduling(
            movie_id,
            allow_deactivated_when_same=movie_id == existing_session["movie_id"],
        )
        self._validate_session_slot(movie=movie, start_time=start_time, end_time=end_time, now=now)

        overlapping = await self.session_repository.find_overlapping(
            start_time=start_time,
            end_time=end_time,
            exclude_session_id=session_id,
        )
        if overlapping is not None:
            raise ConflictException("Session overlaps with an existing session in the only hall.")

        updated_document = await self.session_repository.update_session_if_editable(
            session_id,
            updates={
                "movie_id": movie_id,
                "start_time": start_time,
                "end_time": end_time,
                "price": updates.get("price", existing_session["price"]),
            },
            current_time=now,
            updated_at=now,
        )
        if updated_document is None:
            latest_session = await self.session_repository.get_by_id(session_id)
            if latest_session is None:
                raise NotFoundException("Session was not found.")
            latest_update_blocker = self._get_session_update_blocker(latest_session, now=now)
            if latest_update_blocker is not None:
                raise ConflictException(latest_update_blocker)
            if latest_session["available_seats"] < latest_session["total_seats"]:
                raise ConflictException(
                    "Sessions with purchased tickets cannot be edited. Cancel the session instead."
                )
            raise ConflictException("Session can no longer be edited.")

        await self.movie_status_manager.refresh_statuses(current_time=now)
        return SessionDetailsFactory.build(
            session=SessionRead.model_validate(updated_document),
            movie=await self._get_movie_or_not_found(movie_id),
        )

    async def delete_session(self, session_id: str, deleted_by: UserRead) -> DeleteResultRead:
        """Delete a session only when no tickets have ever been stored for it."""
        _ = deleted_by
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)

        async def delete_transaction(db_session) -> None:
            session = await self.session_repository.get_by_id(session_id, db_session=db_session)
            if session is None:
                raise NotFoundException("Session was not found.")

            stored_tickets = await self.ticket_repository.count_by_session(
                session_id,
                active_only=False,
                db_session=db_session,
            )
            if stored_tickets > 0:
                raise ConflictException("Sessions with stored tickets cannot be deleted. Cancel the session instead.")

            deleted = await self.session_repository.delete_session(session_id, db_session=db_session)
            if not deleted:
                raise NotFoundException("Session was not found.")

        await run_transaction_with_retry(
            delete_transaction,
            operation_name="delete_session",
        )
        await self.movie_status_manager.refresh_statuses(current_time=now)
        return DeleteResultRead(id=session_id)

    async def build_attendance_report(self, requested_by: UserRead) -> AttendanceReportRead:
        """Build an attendance report across all sessions."""
        _ = requested_by
        builder = AttendanceReportBuilder()
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        sessions = [SessionRead.model_validate(document) for document in await self.session_repository.list_all()]
        movies = await self.movie_repository.list_by_ids([session.movie_id for session in sessions])
        movie_map = {movie["id"]: MovieRead.model_validate(movie) for movie in movies}

        for session in sessions:
            movie = movie_map.get(session.movie_id)
            if movie is None:
                continue
            ticket_documents = await self.ticket_repository.list_by_session(session.id, active_only=False)
            active_tickets = [
                ticket
                for ticket in ticket_documents
                if ticket["status"] == TicketStatuses.PURCHASED
            ]
            occupied_seats = {
                (int(ticket["seat_row"]), int(ticket["seat_number"]))
                for ticket in active_tickets
            }
            checked_in_tickets_count = sum(
                1 for ticket in active_tickets if ticket.get("checked_in_at") is not None
            )
            tickets_sold = len(active_tickets)
            summary = AttendanceSessionSummary(
                session_id=session.id,
                movie_title=movie.title,
                start_time=session.start_time,
                status=session.status,
                tickets_sold=tickets_sold,
                checked_in_tickets_count=checked_in_tickets_count,
                unchecked_active_tickets_count=max(tickets_sold - checked_in_tickets_count, 0),
                cancelled_tickets_count=sum(
                    1 for ticket in ticket_documents if ticket["status"] == TicketStatuses.CANCELLED
                ),
                total_seats=session.total_seats,
                available_seats=max(session.total_seats - len(occupied_seats), 0),
                attendance_rate=(tickets_sold / session.total_seats) if session.total_seats else 0,
            )
            builder.add_session(summary)
        return builder.build()

    async def get_attendance_session_details(
        self,
        session_id: str,
        requested_by: UserRead,
    ) -> AttendanceSessionDetailsRead:
        """Return detailed attendance information for one session."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)

        session_document = await self.session_repository.get_by_id(session_id)
        if session_document is None:
            raise NotFoundException("Session was not found.")

        session = SessionRead.model_validate(session_document)
        movie = await self._get_movie_or_not_found(session.movie_id)

        ticket_documents = await self.ticket_repository.list_by_session(session_id, active_only=False)
        active_ticket_documents = [
            ticket
            for ticket in ticket_documents
            if ticket["status"] == TicketStatuses.PURCHASED
        ]
        cancelled_ticket_documents = [
            ticket
            for ticket in ticket_documents
            if ticket["status"] == TicketStatuses.CANCELLED
        ]
        occupied_seats = {
            (int(ticket["seat_row"]), int(ticket["seat_number"]))
            for ticket in active_ticket_documents
        }
        derived_available_seats = max(session.total_seats - len(occupied_seats), 0)
        session_details = SessionDetailsFactory.build(
            session=session,
            movie=movie,
        ).model_copy(update={"available_seats": derived_available_seats})
        seat_map = self._build_session_seat_map(session=session, occupied_seats=occupied_seats)

        user_documents = await self.user_repository.list_by_ids(
            [str(ticket["user_id"]) for ticket in ticket_documents]
        )
        order_documents = await self.order_repository.list_by_ids(
            [
                str(ticket["order_id"])
                for ticket in ticket_documents
                if ticket.get("order_id")
            ]
        )
        user_map = {str(user["id"]): user for user in user_documents}
        order_map = {str(order["id"]): order for order in order_documents}

        occupied_tickets = self._build_attendance_ticket_details(
            active_ticket_documents,
            user_map=user_map,
            order_map=order_map,
        )
        cancelled_tickets = self._build_attendance_ticket_details(
            cancelled_ticket_documents,
            user_map=user_map,
            order_map=order_map,
        )
        checked_in_tickets_count = sum(
            1 for ticket in occupied_tickets if ticket.checked_in_at is not None
        )

        return AttendanceSessionDetailsRead(
            generated_at=now,
            session=session_details,
            seat_map=seat_map,
            tickets_sold=len(occupied_tickets),
            checked_in_tickets_count=checked_in_tickets_count,
            unchecked_active_tickets_count=max(len(occupied_tickets) - checked_in_tickets_count, 0),
            cancelled_tickets_count=len(cancelled_tickets),
            attendance_rate=(len(occupied_tickets) / session.total_seats) if session.total_seats else 0,
            occupied_tickets=occupied_tickets,
            cancelled_tickets=cancelled_tickets,
        )

    def _build_attendance_ticket_details(
        self,
        ticket_documents: list[dict[str, object]],
        *,
        user_map: dict[str, dict[str, object]],
        order_map: dict[str, dict[str, object]],
    ) -> list[AttendanceTicketDetailsRead]:
        """Build staff-facing ticket rows enriched with safe user and order context."""
        return [
            AttendanceTicketDetailsRead(
                **ticket,
                user_name=str(user["name"]) if user is not None else None,
                user_email=str(user["email"]) if user is not None else None,
                order_status=str(order["status"]) if order is not None else None,
            )
            for ticket, user, order in (
                (
                    ticket,
                    user_map.get(str(ticket["user_id"])),
                    order_map.get(str(ticket["order_id"])) if ticket.get("order_id") else None,
                )
                for ticket in sorted(
                    ticket_documents,
                    key=lambda document: (
                        int(document["seat_row"]),
                        int(document["seat_number"]),
                        document["purchased_at"],
                    ),
                )
            )
        ]

    def _validate_start_time(self, start_time: datetime) -> None:
        settings = get_settings()
        earliest = time(hour=settings.first_session_hour, minute=0)
        latest = time(hour=settings.last_session_start_hour, minute=0)
        local_start_time = start_time.astimezone(ZoneInfo(settings.cinema_timezone))
        candidate = local_start_time.timetz().replace(tzinfo=None)
        if candidate < earliest or candidate > latest:
            raise ValidationException(
                "Session start time must be between "
                f"{earliest.strftime('%H:%M')} and {latest.strftime('%H:%M')}."
            )

    def _normalize_session_time(self, start_time: datetime) -> datetime:
        settings = get_settings()
        cinema_timezone = ZoneInfo(settings.cinema_timezone)
        if start_time.tzinfo is None:
            return start_time.replace(tzinfo=cinema_timezone).astimezone(timezone.utc)
        return start_time.astimezone(timezone.utc)

    def _build_session_seat_map(
        self,
        *,
        session: SessionRead,
        occupied_seats: set[tuple[int, int]],
    ) -> SessionSeatsRead:
        settings = get_settings()
        seats = [
            SeatAvailabilityRead(
                row=row_index,
                number=seat_index,
                is_available=(row_index, seat_index) not in occupied_seats,
            )
            for row_index in range(1, settings.hall_rows_count + 1)
            for seat_index in range(1, settings.hall_seats_per_row + 1)
        ]
        return SessionSeatsRead(
            session_id=session.id,
            rows_count=settings.hall_rows_count,
            seats_per_row=settings.hall_seats_per_row,
            total_seats=session.total_seats,
            available_seats=max(session.total_seats - len(occupied_seats), 0),
            seats=seats,
        )

    def _build_session_window_for_date(
        self,
        *,
        template_start_time: datetime,
        template_end_time: datetime,
        target_date: date,
    ) -> tuple[datetime, datetime]:
        cinema_timezone = ZoneInfo(get_settings().cinema_timezone)
        localized_start = template_start_time.astimezone(cinema_timezone)
        localized_end = template_end_time.astimezone(cinema_timezone)
        duration = localized_end - localized_start

        start_local = datetime.combine(
            target_date,
            localized_start.timetz().replace(tzinfo=None),
            tzinfo=cinema_timezone,
        )
        end_local = start_local + duration
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    async def _require_movie_for_scheduling(
        self,
        movie_id: str,
        *,
        allow_deactivated_when_same: bool = False,
    ) -> MovieRead:
        movie = await self._get_movie_or_not_found(movie_id)
        if movie.status == MovieStatuses.DEACTIVATED and not allow_deactivated_when_same:
            raise ValidationException("Deactivated movies cannot be scheduled. Set the movie back to planned first.")
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
        self._validate_session_window(movie=movie, start_time=start_time, end_time=end_time)

    def _validate_session_window(
        self,
        *,
        movie: MovieRead,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self._validate_start_time(start_time)
        if end_time <= start_time:
            raise ValidationException("Session end time must be greater than start time.")
        slot_duration_minutes = (end_time - start_time).total_seconds() / 60
        if slot_duration_minutes < movie.duration_minutes:
            raise ValidationException("Session slot must be at least as long as the selected movie duration.")
        if slot_duration_minutes > movie.duration_minutes + MAX_SESSION_RUNTIME_BUFFER_MINUTES:
            raise ValidationException(
                "Session slot cannot exceed the movie runtime by more than 60 minutes."
            )

    def _build_session_document(
        self,
        *,
        movie_id: str,
        start_time: datetime,
        end_time: datetime,
        price: float,
        created_at: datetime,
    ) -> dict[str, object]:
        settings = get_settings()
        return {
            "movie_id": movie_id,
            "start_time": start_time,
            "end_time": end_time,
            "price": price,
            "status": SessionStatuses.SCHEDULED,
            "total_seats": settings.total_seats,
            "available_seats": settings.total_seats,
            "created_at": created_at,
            "updated_at": None,
        }

    def _normalize_movie_document(self, document: dict[str, object]) -> dict[str, object]:
        """Convert Pydantic values into plain MongoDB-friendly data."""
        normalized = dict(document)
        if normalized.get("poster_url") is not None:
            normalized["poster_url"] = str(normalized["poster_url"])
        return normalized

    async def _get_movie_or_not_found(self, movie_id: str) -> MovieRead:
        movie_document = await self.movie_repository.get_by_id(movie_id)
        if movie_document is None:
            raise NotFoundException("Movie was not found.")
        return MovieRead.model_validate(movie_document)

    async def _validate_requested_movie_status(
        self,
        *,
        movie_id: str,
        requested_status: str,
        current_time: datetime,
    ) -> None:
        has_future_sessions = await self.movie_status_manager.has_future_sessions(
            movie_id,
            current_time=current_time,
        )
        if requested_status == MovieStatuses.ACTIVE and not has_future_sessions:
            raise ValidationException(
                "Movies become active automatically after a future session is scheduled."
            )
        if requested_status != MovieStatuses.ACTIVE and has_future_sessions:
            raise ConflictException(
                "Movies with future scheduled sessions stay active. Update or cancel those sessions first."
            )

    def _get_session_update_blocker(self, session_document: dict[str, object], *, now: datetime) -> str | None:
        if session_document["status"] == SessionStatuses.CANCELLED:
            return "Cancelled sessions cannot be edited."
        if session_document["status"] == SessionStatuses.COMPLETED:
            return "Completed sessions cannot be edited."
        if session_document["status"] != SessionStatuses.SCHEDULED:
            return "Only scheduled sessions can be edited."
        if session_document["start_time"] <= now:
            return "Only future scheduled sessions can be edited."
        if session_document["available_seats"] < session_document["total_seats"]:
            return "Sessions with purchased tickets cannot be edited. Cancel the session instead."
        return None
