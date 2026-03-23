"""Ticket service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone

from app.commands.ticket_purchase import TicketPurchaseCommand
from app.core.constants import Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import ConflictException, NotFoundException, AuthorizationException
from app.observers.events import build_default_event_publisher
from app.repositories.movies import MovieRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.schemas.movie import MovieRead
from app.schemas.session import SessionRead
from app.schemas.ticket import TicketListRead, TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead


class TicketService:
    """Service encapsulating ticket-related use cases."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        movie_repository: MovieRepository,
        user_repository: UserRepository,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.movie_repository = movie_repository
        self.user_repository = user_repository
        self.event_publisher = build_default_event_publisher()

    async def purchase_ticket(self, payload: TicketPurchaseRequest, current_user: UserRead) -> TicketRead:
        """Purchase a ticket via a command object."""
        command = TicketPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            event_publisher=self.event_publisher,
        )
        return await command.execute(payload=payload, current_user=current_user)

    async def cancel_ticket(self, ticket_id: str, current_user: UserRead) -> TicketRead:
        """Cancel a purchased ticket before the linked session starts."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        ticket_document = await self.ticket_repository.get_by_id(ticket_id)
        if ticket_document is None:
            raise NotFoundException("Ticket was not found.")
        if ticket_document["status"] != TicketStatuses.PURCHASED:
            raise ConflictException("Only purchased tickets can be cancelled.")
        if current_user.role != Roles.ADMIN and ticket_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only cancel your own tickets.")

        session_document = await self.session_repository.get_by_id(ticket_document["session_id"])
        if session_document is None:
            raise NotFoundException("Session for this ticket was not found.")
        if not self._is_ticket_cancellable(ticket_document, session_document, now):
            raise ConflictException("Tickets can only be cancelled before the session starts.")

        updated_ticket = await self.ticket_repository.update_status(
            ticket_id,
            status=TicketStatuses.CANCELLED,
            updated_at=now,
            cancelled_at=now,
        )
        if updated_ticket is None:
            raise NotFoundException("Ticket was not found.")

        seats_restored = await self.session_repository.increment_available_seats(
            ticket_document["session_id"],
            updated_at=now,
        )
        if not seats_restored:
            await self.ticket_repository.update_status(
                ticket_id,
                status=TicketStatuses.PURCHASED,
                updated_at=now,
                cancelled_at=None,
            )
            raise ConflictException("Ticket cancellation could not restore the session seat counter.")

        return TicketRead.model_validate(updated_ticket)

    async def list_current_user_tickets(self, current_user: UserRead) -> list[TicketListRead]:
        """Return tickets belonging to the authenticated user."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        tickets = await self.ticket_repository.list_by_user(current_user.id)
        return await self._build_ticket_list(tickets, include_user_details=False)

    async def list_admin_tickets(self, requested_by: UserRead) -> list[TicketListRead]:
        """Return all tickets for admin dashboards."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        tickets = await self.ticket_repository.list_all()
        return await self._build_ticket_list(tickets, include_user_details=True)

    async def _build_ticket_list(
        self,
        ticket_documents: list[dict[str, object]],
        *,
        include_user_details: bool,
    ) -> list[TicketListRead]:
        session_documents = await self.session_repository.list_by_ids(
            [str(ticket["session_id"]) for ticket in ticket_documents]
        )
        session_map = {
            session["id"]: SessionRead.model_validate(session)
            for session in session_documents
        }
        movie_documents = await self.movie_repository.list_by_ids(
            [session.movie_id for session in session_map.values()]
        )
        movie_map = {
            movie["id"]: MovieRead.model_validate(movie)
            for movie in movie_documents
        }
        user_map: dict[str, dict[str, object]] = {}
        if include_user_details:
            users = await self.user_repository.list_by_ids(
                [str(ticket["user_id"]) for ticket in ticket_documents]
            )
            user_map = {str(user["id"]): user for user in users}

        now = datetime.now(tz=timezone.utc)
        result: list[TicketListRead] = []
        for document in ticket_documents:
            ticket = TicketRead.model_validate(document)
            session = session_map.get(ticket.session_id)
            if session is None:
                continue
            movie = movie_map.get(session.movie_id)
            if movie is None:
                continue

            user = user_map.get(ticket.user_id)
            result.append(
                TicketListRead(
                    **ticket.model_dump(mode="python"),
                    movie_id=movie.id,
                    movie_title=movie.title,
                    session_start_time=session.start_time,
                    session_end_time=session.end_time,
                    session_status=session.status,
                    is_cancellable=self._is_ticket_cancellable(document, session.model_dump(mode="python"), now),
                    user_name=str(user["name"]) if user is not None else None,
                    user_email=str(user["email"]) if user is not None else None,
                )
            )
        return result

    def _is_ticket_cancellable(
        self,
        ticket_document: dict[str, object],
        session_document: dict[str, object],
        now: datetime,
    ) -> bool:
        return (
            ticket_document["status"] == TicketStatuses.PURCHASED
            and session_document["status"] == SessionStatuses.SCHEDULED
            and session_document["start_time"] > now
        )
