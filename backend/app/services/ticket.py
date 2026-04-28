"""Ticket service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone

from app.commands.ticket_cancellation import TicketCancellationCommand
from app.commands.ticket_purchase import TicketPurchaseCommand
from app.core.constants import SessionStatuses, TicketStatuses
from app.observers.events import build_default_event_publisher
from app.repositories.movies import MovieRepository
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.schemas.movie import MovieRead
from app.schemas.session import SessionRead
from app.schemas.ticket import TicketListRead, TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead
from app.security.order_validation import create_order_validation_token


class TicketService:
    """Service encapsulating ticket-related use cases."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        order_repository: OrderRepository,
        movie_repository: MovieRepository,
        user_repository: UserRepository,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.order_repository = order_repository
        self.movie_repository = movie_repository
        self.user_repository = user_repository
        self.event_publisher = build_default_event_publisher()

    async def purchase_ticket(self, payload: TicketPurchaseRequest, current_user: UserRead) -> TicketRead:
        """Purchase a ticket via a command object."""
        command = TicketPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
            event_publisher=self.event_publisher,
        )
        return await command.execute(payload=payload, current_user=current_user)

    async def cancel_ticket(self, ticket_id: str, current_user: UserRead) -> TicketRead:
        """Cancel a purchased ticket before the linked session starts."""
        command = TicketCancellationCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
        )
        return await command.execute(ticket_id=ticket_id, current_user=current_user)

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
        order_ids = [
            str(ticket["order_id"])
            for ticket in ticket_documents
            if ticket.get("order_id")
        ]
        order_documents = await self.order_repository.list_by_ids(order_ids)
        order_map = {str(order["id"]): order for order in order_documents}

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
            order = order_map.get(str(ticket.order_id)) if ticket.order_id else None
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
                    order_status=str(order["status"]) if order is not None else None,
                    order_created_at=order.get("created_at") if order is not None else None,
                    order_total_price=float(order["total_price"]) if order is not None else None,
                    order_tickets_count=int(order["tickets_count"]) if order is not None else None,
                    order_validation_token=(
                        create_order_validation_token(str(order["id"]))
                        if order is not None and include_user_details
                        else None
                    ),
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
            and session_document["status"] in {SessionStatuses.SCHEDULED, SessionStatuses.CANCELLED}
            and session_document["start_time"] > now
            and ticket_document.get("checked_in_at") is None
        )
