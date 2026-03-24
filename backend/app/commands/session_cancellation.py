"""Command handling session cancellation workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.constants import SessionStatuses
from app.core.exceptions import ConflictException, NotFoundException
from app.observers.events import EventPublisher, new_session_cancelled_event
from app.repositories.sessions import SessionRepository
from app.schemas.session import SessionRead
from app.schemas.user import UserRead


class SessionCancellationCommand:
    """Encapsulate the session cancellation use case."""

    def __init__(
        self,
        session_repository: SessionRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self.session_repository = session_repository
        self.event_publisher = event_publisher

    async def execute(self, session_id: str, cancelled_by: UserRead) -> SessionRead:
        """Cancel the given session and emit a domain event."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        existing_session = await self.session_repository.get_by_id(session_id)
        if existing_session is None:
            raise NotFoundException("Session was not found.")
        cancellation_blocker = self._get_cancellation_blocker(existing_session, now=now)
        if cancellation_blocker is not None:
            raise ConflictException(cancellation_blocker)

        updated_session = await self.session_repository.cancel_future_scheduled_session(
            session_id=session_id,
            current_time=now,
            updated_at=now,
        )
        if updated_session is None:
            latest_session = await self.session_repository.get_by_id(session_id)
            if latest_session is None:
                raise NotFoundException("Session was not found.")
            latest_blocker = self._get_cancellation_blocker(latest_session, now=now)
            raise ConflictException(latest_blocker or "Session can no longer be cancelled.")

        await self.event_publisher.publish(
            new_session_cancelled_event(
                {
                    "session_id": session_id,
                    "cancelled_by": cancelled_by.id,
                }
            )
        )
        return SessionRead.model_validate(updated_session)

    def _get_cancellation_blocker(self, session_document: dict[str, object], *, now: datetime) -> str | None:
        if session_document["status"] == SessionStatuses.CANCELLED:
            return "Session has already been cancelled."
        if session_document["status"] == SessionStatuses.COMPLETED:
            return "Completed sessions cannot be cancelled."
        if session_document["status"] != SessionStatuses.SCHEDULED:
            return "Only scheduled sessions can be cancelled."
        if session_document["start_time"] <= now:
            return "Only future scheduled sessions can be cancelled."
        return None
