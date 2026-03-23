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
        existing_session = await self.session_repository.get_by_id(session_id)
        if existing_session is None:
            raise NotFoundException("Session was not found.")
        if existing_session["status"] != SessionStatuses.SCHEDULED:
            raise ConflictException("Only scheduled sessions can be cancelled.")
        if existing_session["start_time"] <= datetime.now(tz=timezone.utc):
            raise ConflictException("Only future scheduled sessions can be cancelled.")

        updated_session = await self.session_repository.update_status(
            session_id=session_id,
            status=SessionStatuses.CANCELLED,
            updated_at=datetime.now(tz=timezone.utc),
        )
        if updated_session is None:
            raise NotFoundException("Session was not found.")

        await self.event_publisher.publish(
            new_session_cancelled_event(
                {
                    "session_id": session_id,
                    "cancelled_by": cancelled_by.id,
                }
            )
        )
        return SessionRead.model_validate(updated_session)
