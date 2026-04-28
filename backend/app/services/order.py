"""Order service for grouped ticket purchases and order history."""

from __future__ import annotations

from datetime import datetime, timezone

from app.builders.order_pdf import build_order_pdf
from app.commands.order_cancellation import OrderCancellationCommand
from app.commands.order_purchase import OrderPurchaseCommand
from app.core.config import get_settings
from app.core.constants import OrderStatuses, Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import AuthorizationException, ConflictException, NotFoundException
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
    OrderValidationRead,
    OrderValidationTicketRead,
)
from app.schemas.session import SessionRead
from app.schemas.user import UserRead
from app.security.order_validation import create_order_validation_token, decode_order_validation_token
from app.utils.identifiers import is_valid_object_id
from app.utils.order_aggregates import build_order_aggregate_updates

VALIDATION_STATE_VALID = "valid"
VALIDATION_STATE_CANCELLED = "cancelled"
VALIDATION_STATE_EXPIRED = "expired"
VALIDATION_STATE_ALREADY_USED = "already_used"


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

        now = datetime.now(tz=timezone.utc)
        built_order = self._build_order_read(
            order_document=result["order"],
            ticket_documents=result["tickets"],
            session_document=session_document,
            movie_document=movie_document,
            now=now,
        )
        return self._build_order_details(order=built_order, now=now)

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
        return self._build_order_details(order=built_orders[0], now=now)

    async def build_current_user_order_pdf(self, order_id: str, current_user: UserRead) -> bytes:
        """Build a PDF receipt for one order owned by the current user."""
        order = await self.get_current_user_order(order_id=order_id, current_user=current_user)
        return build_order_pdf(order=order, generated_at=datetime.now(tz=timezone.utc))

    async def validate_order_token(self, token: str, requested_by: UserRead) -> OrderValidationRead:
        """Validate a scanned order QR token for staff use."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        payload = decode_order_validation_token(token)
        if payload is None or not is_valid_object_id(payload.sub):
            return self._build_invalid_validation_result(
                scanned_at=now,
                token_status="invalid_token",
                validity_code="invalid_token",
                message="The scanned QR token is not trusted by this cinema system.",
            )

        order_document = await self.order_repository.get_by_id(payload.sub)
        if order_document is None:
            return self._build_invalid_validation_result(
                scanned_at=now,
                token_status="order_not_found",
                validity_code="order_not_found",
                message="The QR token is signed, but the referenced order no longer exists.",
                order_id=payload.sub,
            )

        built_orders = await self._build_order_list([order_document], now=now)
        if not built_orders:
            return self._build_invalid_validation_result(
                scanned_at=now,
                token_status="order_unavailable",
                validity_code="order_unavailable",
                message="The order exists, but its linked session or movie could not be loaded.",
                order_id=payload.sub,
            )

        details = self._build_order_details(order=built_orders[0], now=now)
        return self._build_validation_result(order=details, scanned_at=now)

    async def check_in_order(self, order_id: str, requested_by: UserRead) -> OrderValidationRead:
        """Mark all currently valid unchecked tickets in an order as checked in."""
        _ = requested_by
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")

        built_orders = await self._build_order_list([order_document], now=now)
        if not built_orders:
            raise NotFoundException("Order was not found.")

        current_details = self._build_order_details(order=built_orders[0], now=now)
        if current_details.entry_status_code != VALIDATION_STATE_VALID:
            raise ConflictException(self._get_check_in_blocker_message(current_details.entry_status_code))

        checked_in_count = await self.ticket_repository.check_in_many_by_order(
            order_id,
            checked_in_at=now,
            updated_at=now,
        )
        if checked_in_count <= 0:
            raise ConflictException("Order has already been checked in.")

        refreshed_order_document = await self.order_repository.get_by_id(order_id)
        if refreshed_order_document is None:
            raise NotFoundException("Order was not found.")
        refreshed_orders = await self._build_order_list([refreshed_order_document], now=now)
        if not refreshed_orders:
            raise NotFoundException("Order was not found.")

        refreshed_details = self._build_order_details(order=refreshed_orders[0], now=now)
        return self._build_validation_result(order=refreshed_details, scanned_at=now)

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
            self._build_order_ticket(
                ticket_document=document,
                session=session,
                order_status=order.status,
                now=now,
            )
            for document in ticket_documents
        ]
        active_tickets_count = sum(1 for ticket in tickets if ticket.status == TicketStatuses.PURCHASED)
        cancelled_tickets_count = len(tickets) - active_tickets_count
        checked_in_tickets_count = sum(
            1
            for ticket in tickets
            if ticket.status == TicketStatuses.PURCHASED and ticket.checked_in_at is not None
        )
        unchecked_active_tickets_count = max(active_tickets_count - checked_in_tickets_count, 0)

        return OrderListRead(
            **order.model_dump(mode="python"),
            movie_id=movie.id,
            movie_title=movie.title,
            poster_url=str(movie.poster_url) if movie.poster_url else None,
            age_rating=movie.age_rating,
            session_start_time=session.start_time,
            session_end_time=session.end_time,
            session_price=session.price,
            session_status=session.status,
            active_tickets_count=active_tickets_count,
            cancelled_tickets_count=cancelled_tickets_count,
            checked_in_tickets_count=checked_in_tickets_count,
            unchecked_active_tickets_count=unchecked_active_tickets_count,
            tickets=tickets,
        )

    def _build_order_details(self, *, order: OrderListRead, now: datetime) -> OrderDetailsRead:
        """Add customer-facing validation metadata to an enriched order."""
        is_valid, code, message = self._get_order_validity(order=order, now=now)
        token = create_order_validation_token(order.id)
        return OrderDetailsRead(
            **order.model_dump(mode="python"),
            valid_for_entry=is_valid,
            entry_status_code=code,
            entry_status_message=message,
            validation_token=token,
            validation_url=self._build_validation_url(token),
        )

    def _build_validation_url(self, token: str) -> str:
        """Build the staff-facing frontend URL encoded in order QR codes."""
        settings = get_settings()
        base_url = settings.frontend_base_url.rstrip("/")
        return f"{base_url}/admin/order-validation/{token}"

    def _get_order_validity(self, *, order: OrderListRead, now: datetime) -> tuple[bool, str, str]:
        """Return the admission-state decision for an order QR code."""
        if order.status == OrderStatuses.CANCELLED:
            return False, VALIDATION_STATE_CANCELLED, "The order is fully cancelled."
        if order.active_tickets_count <= 0:
            return False, VALIDATION_STATE_CANCELLED, "The order has no active purchased tickets."
        if order.session_status == SessionStatuses.CANCELLED:
            return False, VALIDATION_STATE_CANCELLED, "The session was cancelled."
        if order.checked_in_tickets_count > 0 and order.unchecked_active_tickets_count <= 0:
            return False, VALIDATION_STATE_ALREADY_USED, "All active tickets in this order were already checked in."
        if order.session_status == SessionStatuses.COMPLETED:
            return False, VALIDATION_STATE_EXPIRED, "The session is already completed."
        if order.session_status != SessionStatuses.SCHEDULED:
            return False, VALIDATION_STATE_EXPIRED, "The session is not available for entry validation."
        if order.session_start_time <= now:
            return False, VALIDATION_STATE_EXPIRED, "The session has already started."

        valid_tickets = [ticket for ticket in order.tickets if ticket.valid_for_entry]
        if not valid_tickets:
            return False, VALIDATION_STATE_ALREADY_USED, "The order has no unchecked tickets currently valid for entry."

        return True, VALIDATION_STATE_VALID, "The order has unchecked active tickets for a future scheduled session."

    def _build_validation_result(self, *, order: OrderDetailsRead, scanned_at: datetime) -> OrderValidationRead:
        """Build staff-facing validation output from live order details."""
        return OrderValidationRead(
            scanned_at=scanned_at,
            token_status="valid_token",
            order_id=order.id,
            is_valid_for_entry=order.valid_for_entry,
            validity_code=order.entry_status_code,
            message=order.entry_status_message,
            can_check_in=order.entry_status_code == VALIDATION_STATE_VALID,
            order_status=order.status,
            movie_title=order.movie_title,
            session_start_time=order.session_start_time,
            session_end_time=order.session_end_time,
            session_status=order.session_status,
            active_tickets_count=order.active_tickets_count,
            cancelled_tickets_count=order.cancelled_tickets_count,
            checked_in_tickets_count=order.checked_in_tickets_count,
            unchecked_active_tickets_count=order.unchecked_active_tickets_count,
            tickets=[
                OrderValidationTicketRead(
                    id=ticket.id,
                    seat_row=ticket.seat_row,
                    seat_number=ticket.seat_number,
                    status=ticket.status,
                    purchased_at=ticket.purchased_at,
                    cancelled_at=ticket.cancelled_at,
                    checked_in_at=ticket.checked_in_at,
                    valid_for_entry=ticket.valid_for_entry,
                )
                for ticket in order.tickets
            ],
        )

    def _build_invalid_validation_result(
        self,
        *,
        scanned_at: datetime,
        token_status: str,
        validity_code: str,
        message: str,
        order_id: str | None = None,
    ) -> OrderValidationRead:
        """Build a validation response for malformed or stale QR payloads."""
        return OrderValidationRead(
            scanned_at=scanned_at,
            token_status=token_status,
            order_id=order_id,
            is_valid_for_entry=False,
            validity_code=validity_code,
            message=message,
        )

    def _build_order_ticket(
        self,
        *,
        ticket_document: dict[str, object],
        session: SessionRead,
        now: datetime,
        order_status: str = OrderStatuses.COMPLETED,
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
            checked_in_at=ticket_document.get("checked_in_at"),
            is_cancellable=self._is_ticket_cancellable(
                ticket_document=ticket_document,
                session_document=session,
                now=now,
            ),
            valid_for_entry=self._is_ticket_valid_for_entry(
                ticket_document=ticket_document,
                session_document=session,
                order_status=order_status,
                now=now,
            ),
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
            and ticket_document.get("checked_in_at") is None
        )

    def _is_ticket_valid_for_entry(
        self,
        *,
        ticket_document: dict[str, object],
        session_document: SessionRead,
        order_status: str,
        now: datetime,
    ) -> bool:
        """Return whether one ticket can currently be accepted at entry."""
        return (
            ticket_document["status"] == TicketStatuses.PURCHASED
            and order_status != OrderStatuses.CANCELLED
            and session_document.status == SessionStatuses.SCHEDULED
            and session_document.start_time > now
            and ticket_document.get("checked_in_at") is None
        )

    def _get_check_in_blocker_message(self, validation_state: str) -> str:
        """Return a staff-facing conflict message for a blocked check-in."""
        if validation_state == VALIDATION_STATE_ALREADY_USED:
            return "Order has already been checked in."
        if validation_state == VALIDATION_STATE_CANCELLED:
            return "Cancelled orders or tickets cannot be checked in."
        if validation_state == VALIDATION_STATE_EXPIRED:
            return "Expired orders cannot be checked in."
        return "Order cannot be checked in."

    def _ensure_order_owner(self, *, order_document: dict[str, object], current_user: UserRead) -> None:
        """Prevent users from reading orders that do not belong to them."""
        if current_user.role != Roles.ADMIN and order_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only access your own orders.")
