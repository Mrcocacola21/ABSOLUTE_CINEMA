"""Ticket service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.commands.ticket_purchase import TicketPurchaseCommand
from app.core.constants import OrderStatuses, Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import (
    AuthorizationException,
    ConflictException,
    DatabaseException,
    NotFoundException,
)
from app.db.transactions import mongo_transaction
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
from app.utils.session_locks import session_write_lock


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
        async with session_write_lock(payload.session_id):
            command = TicketPurchaseCommand(
                session_repository=self.session_repository,
                ticket_repository=self.ticket_repository,
                order_repository=self.order_repository,
                event_publisher=self.event_publisher,
            )
            return await command.execute(payload=payload, current_user=current_user)

    async def cancel_ticket(self, ticket_id: str, current_user: UserRead) -> TicketRead:
        """Cancel a purchased ticket before the linked session starts."""
        ticket_document = await self.ticket_repository.get_by_id(ticket_id)
        if ticket_document is None:
            raise NotFoundException("Ticket was not found.")
        self._ensure_ticket_owner(ticket_document=ticket_document, current_user=current_user)

        async with session_write_lock(str(ticket_document["session_id"])):
            now = datetime.now(tz=timezone.utc)
            await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
            updated_ticket: dict[str, object] | None = None
            try:
                async with mongo_transaction() as db_session:
                    ticket_document = await self.ticket_repository.get_by_id(ticket_id, db_session=db_session)
                    if ticket_document is None:
                        raise NotFoundException("Ticket was not found.")
                    self._ensure_ticket_owner(ticket_document=ticket_document, current_user=current_user)

                    session_document = await self.session_repository.get_by_id(
                        ticket_document["session_id"],
                        db_session=db_session,
                    )
                    if session_document is None:
                        raise NotFoundException("Session for this ticket was not found.")
                    cancellation_blocker = self._get_ticket_cancellation_blocker(
                        ticket_document=ticket_document,
                        session_document=session_document,
                        now=now,
                    )
                    if cancellation_blocker is not None:
                        raise ConflictException(cancellation_blocker)

                    updated_ticket = await self.ticket_repository.update_status(
                        ticket_id,
                        status=TicketStatuses.CANCELLED,
                        updated_at=now,
                        cancelled_at=now,
                        current_status=TicketStatuses.PURCHASED,
                        db_session=db_session,
                    )
                    if updated_ticket is None:
                        raise ConflictException("Ticket can no longer be cancelled.")

                    seats_restored = await self.session_repository.increment_available_seats(
                        ticket_document["session_id"],
                        updated_at=now,
                        db_session=db_session,
                    )
                    if not seats_restored:
                        raise DatabaseException(
                            "Ticket cancellation could not restore the session seat counter."
                        )

                    order_id = str(ticket_document.get("order_id") or "")
                    if order_id:
                        await self._refresh_order_aggregate(
                            order_id,
                            updated_at=now,
                            db_session=db_session,
                        )
            except Exception as exc:
                if isinstance(exc, (AuthorizationException, ConflictException, DatabaseException, NotFoundException)):
                    raise
                raise DatabaseException("Unable to cancel the ticket.") from exc

            if updated_ticket is None:
                raise DatabaseException("Ticket cancellation did not produce an updated ticket.")
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
            and session_document["status"] in {SessionStatuses.SCHEDULED, SessionStatuses.CANCELLED}
            and session_document["start_time"] > now
        )

    def _get_ticket_cancellation_blocker(
        self,
        *,
        ticket_document: dict[str, object],
        session_document: dict[str, object],
        now: datetime,
    ) -> str | None:
        if ticket_document["status"] == TicketStatuses.CANCELLED:
            return "Ticket has already been cancelled."
        if ticket_document["status"] != TicketStatuses.PURCHASED:
            return "Only purchased tickets can be cancelled."
        if session_document["status"] == SessionStatuses.COMPLETED:
            return "Tickets for completed sessions cannot be cancelled."
        if session_document["status"] not in {SessionStatuses.SCHEDULED, SessionStatuses.CANCELLED}:
            return "Only tickets for scheduled or cancelled sessions can be cancelled."
        if session_document["start_time"] <= now:
            return "Tickets can only be cancelled before the session starts."
        return None

    def _ensure_ticket_owner(
        self,
        *,
        ticket_document: dict[str, object],
        current_user: UserRead,
    ) -> None:
        if current_user.role != Roles.ADMIN and ticket_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only cancel your own tickets.")

    async def _refresh_order_aggregate(
        self,
        order_id: str,
        *,
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> None:
        """Keep the stored order summary aligned with current ticket statuses."""
        order_document = await self.order_repository.get_by_id(order_id, db_session=db_session)
        if order_document is None:
            raise DatabaseException("Order for this ticket was not found.")

        ticket_documents = await self.ticket_repository.list_by_order(order_id, db_session=db_session)
        if not ticket_documents:
            raise DatabaseException("Order aggregate could not be refreshed because no tickets were found.")

        active_tickets_count = sum(
            1 for ticket in ticket_documents if ticket["status"] == TicketStatuses.PURCHASED
        )
        if active_tickets_count <= 0:
            derived_status = OrderStatuses.CANCELLED
        elif active_tickets_count == len(ticket_documents):
            derived_status = OrderStatuses.COMPLETED
        else:
            derived_status = OrderStatuses.PARTIALLY_CANCELLED

        updates: dict[str, object] = {}
        if order_document.get("status") != derived_status:
            updates["status"] = derived_status

        derived_total_price = float(sum(float(ticket["price"]) for ticket in ticket_documents))
        if int(order_document.get("tickets_count", 0)) != len(ticket_documents):
            updates["tickets_count"] = len(ticket_documents)
        if float(order_document.get("total_price", 0)) != derived_total_price:
            updates["total_price"] = derived_total_price

        if not updates:
            return

        await self.order_repository.update_order(
            order_id,
            updates=updates,
            updated_at=updated_at,
            db_session=db_session,
        )
