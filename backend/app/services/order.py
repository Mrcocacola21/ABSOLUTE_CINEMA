"""Order service for grouped ticket purchases and order history."""

from __future__ import annotations

from datetime import datetime, timezone

from app.commands.order_cancellation import OrderCancellationCommand
from app.commands.order_purchase import OrderPurchaseCommand
from app.core.constants import Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import AuthorizationException, NotFoundException
from app.observers.events import build_default_event_publisher
from app.repositories.movies import MovieRepository
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.movie import MovieRead
from app.schemas.order import (
    OrderDetailsRead,
    OrderListRead,
    OrderPurchaseRequest,
    OrderRead,
    OrderTicketRead,
)
from app.schemas.session import SessionRead
from app.schemas.user import UserRead
from app.utils.order_aggregates import build_order_aggregate_updates


class OrderService:
    """Service encapsulating grouped order purchase and read use cases."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        movie_repository: MovieRepository,
        order_repository: OrderRepository,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.movie_repository = movie_repository
        self.order_repository = order_repository
        self.event_publisher = build_default_event_publisher()

    async def purchase_order(self, payload: OrderPurchaseRequest, current_user: UserRead) -> OrderDetailsRead:
        """Purchase multiple seats for one session as a single order."""
        command = OrderPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
            event_publisher=self.event_publisher,
        )
        result = await command.execute(payload=payload, current_user=current_user)

        session_document = await self.session_repository.get_by_id(payload.session_id)
        if session_document is None:
            raise NotFoundException("Session was not found.")
        movie_document = await self.movie_repository.get_by_id(str(session_document["movie_id"]))
        if movie_document is None:
            raise NotFoundException("Movie for this session was not found.")

        built_order = self._build_order_read(
            order_document=result["order"],
            ticket_documents=result["tickets"],
            session_document=session_document,
            movie_document=movie_document,
            now=datetime.now(tz=timezone.utc),
        )
        return OrderDetailsRead.model_validate(built_order.model_dump(mode="python"))

    async def cancel_order(self, order_id: str, current_user: UserRead) -> OrderDetailsRead:
        """Cancel all active tickets contained in one order."""
        command = OrderCancellationCommand(
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            session_repository=self.session_repository,
        )
        await command.execute(order_id=order_id, current_user=current_user)
        return await self.get_current_user_order(order_id=order_id, current_user=current_user)

    async def list_current_user_orders(self, current_user: UserRead) -> list[OrderListRead]:
        """Return orders belonging to the authenticated user."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        orders = await self.order_repository.list_by_user(current_user.id)
        return await self._build_order_list(orders, now=now)

    async def get_current_user_order(self, order_id: str, current_user: UserRead) -> OrderDetailsRead:
        """Return one order belonging to the authenticated user."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        self._ensure_order_owner(order_document=order_document, current_user=current_user)

        built_orders = await self._build_order_list([order_document], now=now)
        if not built_orders:
            raise NotFoundException("Order was not found.")
        return OrderDetailsRead.model_validate(built_orders[0].model_dump(mode="python"))

    async def _build_order_list(
        self,
        order_documents: list[dict[str, object]],
        *,
        now: datetime,
    ) -> list[OrderListRead]:
        """Enrich raw order documents with session, movie, and ticket details."""
        if not order_documents:
            return []

        session_documents = await self.session_repository.list_by_ids(
            [str(order["session_id"]) for order in order_documents]
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

        result: list[OrderListRead] = []
        for order_document in order_documents:
            session = session_map.get(str(order_document["session_id"]))
            if session is None:
                continue
            movie = movie_map.get(session.movie_id)
            if movie is None:
                continue

            tickets = await self.ticket_repository.list_by_order(str(order_document["id"]))
            if not tickets:
                continue

            normalized_order = await self._synchronize_order_aggregate(
                order_document=order_document,
                ticket_documents=tickets,
                updated_at=now,
            )
            result.append(
                self._build_order_read(
                    order_document=normalized_order,
                    ticket_documents=tickets,
                    session_document=session.model_dump(mode="python"),
                    movie_document=movie.model_dump(mode="python"),
                    now=now,
                )
            )
        return result

    async def _synchronize_order_aggregate(
        self,
        *,
        order_document: dict[str, object],
        ticket_documents: list[dict[str, object]],
        updated_at: datetime,
    ) -> dict[str, object]:
        """Keep stored order aggregate fields aligned with nested tickets."""
        updates = build_order_aggregate_updates(
            order_document=order_document,
            ticket_documents=ticket_documents,
        )
        if not updates:
            return order_document

        updated_order = await self.order_repository.update_order(
            str(order_document["id"]),
            updates=updates,
            updated_at=updated_at,
        )
        return updated_order or {**order_document, **updates, "updated_at": updated_at}

    def _build_order_read(
        self,
        *,
        order_document: dict[str, object],
        ticket_documents: list[dict[str, object]],
        session_document: dict[str, object],
        movie_document: dict[str, object],
        now: datetime,
    ) -> OrderListRead:
        """Build one enriched order DTO."""
        order = OrderRead.model_validate(order_document)
        session = SessionRead.model_validate(session_document)
        movie = MovieRead.model_validate(movie_document)
        tickets = [
            self._build_order_ticket(ticket_document=document, session=session, now=now)
            for document in ticket_documents
        ]
        active_tickets_count = sum(1 for ticket in tickets if ticket.status == TicketStatuses.PURCHASED)
        cancelled_tickets_count = len(tickets) - active_tickets_count

        return OrderListRead(
            **order.model_dump(mode="python"),
            movie_id=movie.id,
            movie_title=movie.title,
            poster_url=movie.poster_url,
            age_rating=movie.age_rating,
            session_start_time=session.start_time,
            session_end_time=session.end_time,
            session_status=session.status,
            active_tickets_count=active_tickets_count,
            cancelled_tickets_count=cancelled_tickets_count,
            tickets=tickets,
        )

    def _build_order_ticket(
        self,
        *,
        ticket_document: dict[str, object],
        session: SessionRead,
        now: datetime,
    ) -> OrderTicketRead:
        """Build one nested ticket DTO inside an order response."""
        return OrderTicketRead(
            id=str(ticket_document["id"]),
            order_id=str(ticket_document.get("order_id")) if ticket_document.get("order_id") else None,
            seat_row=int(ticket_document["seat_row"]),
            seat_number=int(ticket_document["seat_number"]),
            price=float(ticket_document["price"]),
            status=str(ticket_document["status"]),
            purchased_at=ticket_document["purchased_at"],
            updated_at=ticket_document.get("updated_at"),
            cancelled_at=ticket_document.get("cancelled_at"),
            is_cancellable=self._is_ticket_cancellable(ticket_document=ticket_document, session_document=session, now=now),
        )

    def _is_ticket_cancellable(
        self,
        *,
        ticket_document: dict[str, object],
        session_document: SessionRead,
        now: datetime,
    ) -> bool:
        """Return whether an order ticket can still be cancelled."""
        return (
            ticket_document["status"] == TicketStatuses.PURCHASED
            and session_document.status in {SessionStatuses.SCHEDULED, SessionStatuses.CANCELLED}
            and session_document.start_time > now
        )

    def _ensure_order_owner(self, *, order_document: dict[str, object], current_user: UserRead) -> None:
        """Prevent users from reading orders that do not belong to them."""
        if current_user.role != Roles.ADMIN and order_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only access your own orders.")
