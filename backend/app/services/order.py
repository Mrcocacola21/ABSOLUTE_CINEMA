"""Order service for grouped ticket purchases and order history."""

from __future__ import annotations

from datetime import datetime, timezone

from app.builders.order_pdf import build_order_pdf
from app.commands.order_cancellation import OrderCancellationCommand
from app.commands.order_finalization import OrderFinalizationCommand
from app.commands.order_purchase import OrderPurchaseCommand
from app.commands.reservation_expiry import sync_expired_reservations_for_session
from app.core.config import get_settings
from app.core.constants import OrderStatuses, PaymentStatuses, RefundStatuses, Roles, SessionStatuses, TicketStatuses
from app.core.exceptions import AuthorizationException, ConflictException, NotFoundException
from app.core.logging import get_audit_logger
from app.observers.events import build_default_event_publisher
from app.repositories.movies import MovieRepository
from app.repositories.orders import OrderRepository
from app.repositories.payments import PaymentRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.movie import MovieRead, resolve_movie_poster_url
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
from app.services.refund import RefundService
from app.utils.identifiers import is_valid_object_id
from app.utils.money import amount_to_minor_units
from app.utils.order_aggregates import build_order_aggregate_updates

VALIDATION_STATE_VALID = "valid"
VALIDATION_STATE_CANCELLED = "cancelled"
VALIDATION_STATE_EXPIRED = "expired"
VALIDATION_STATE_ALREADY_USED = "already_used"
ORDER_REFUND_RESERVED_STATUSES = {
    RefundStatuses.CREATED,
    RefundStatuses.PENDING,
    RefundStatuses.SUCCEEDED,
}
ORDER_REFUNDABLE_PAYMENT_STATUSES = {
    PaymentStatuses.SUCCEEDED,
    PaymentStatuses.PARTIALLY_REFUNDED,
}
audit_logger = get_audit_logger(__name__)


class OrderService:
    """Service encapsulating grouped order purchase and read use cases."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        movie_repository: MovieRepository,
        order_repository: OrderRepository,
        payment_repository: PaymentRepository | None = None,
        refund_service: RefundService | None = None,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.movie_repository = movie_repository
        self.order_repository = order_repository
        self.payment_repository = payment_repository
        self.refund_service = refund_service
        self.event_publisher = build_default_event_publisher()

    async def purchase_order(self, payload: OrderPurchaseRequest, current_user: UserRead) -> OrderDetailsRead:
        """Reserve multiple seats for one session as a pending payment order."""
        command = OrderPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
            event_publisher=self.event_publisher,
            payment_repository=self.payment_repository,
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
        """Cancel all active reserved or purchased tickets contained in one order."""
        command = OrderCancellationCommand(
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            session_repository=self.session_repository,
        )
        await command.execute(order_id=order_id, current_user=current_user)
        return await self.get_current_user_order(order_id=order_id, current_user=current_user)

    async def finalize_pending_order(self, order_id: str) -> OrderRead:
        """Internal hook for a future payment success flow."""
        command = OrderFinalizationCommand(
            order_repository=self.order_repository,
            ticket_repository=self.ticket_repository,
            session_repository=self.session_repository,
        )
        finalized = await command.execute(order_id=order_id)
        return OrderRead.model_validate(finalized)

    async def list_current_user_orders(self, current_user: UserRead) -> list[OrderListRead]:
        """Return orders belonging to the authenticated user."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)
        orders = await self.order_repository.list_by_user(current_user.id)
        orders = await self._sync_expired_reservations_for_orders(orders, now=now)
        return await self._build_order_list(orders, now=now)

    async def get_current_user_order(self, order_id: str, current_user: UserRead) -> OrderDetailsRead:
        """Return one order belonging to the authenticated user."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        self._ensure_order_owner(order_document=order_document, current_user=current_user)
        synced_orders = await self._sync_expired_reservations_for_orders([order_document], now=now)
        order_document = synced_orders[0] if synced_orders else order_document

        built_orders = await self._build_order_list([order_document], now=now)
        if not built_orders:
            raise NotFoundException("Order was not found.")
        return self._build_order_details(order=built_orders[0], now=now)

    async def build_current_user_order_pdf(self, order_id: str, current_user: UserRead) -> bytes:
        """Build a PDF receipt for one order owned by the current user."""
        order = await self.get_current_user_order(order_id=order_id, current_user=current_user)
        if order.status not in {OrderStatuses.COMPLETED, OrderStatuses.PARTIALLY_CANCELLED}:
            raise ConflictException("PDF receipt is available after payment is completed.")
        return build_order_pdf(order=order, generated_at=datetime.now(tz=timezone.utc))

    async def validate_order_token(self, token: str, requested_by: UserRead) -> OrderValidationRead:
        """Validate a scanned order QR token for staff use."""
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
        synced_orders = await self._sync_expired_reservations_for_orders([order_document], now=now)
        order_document = synced_orders[0] if synced_orders else order_document

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
        result = self._build_validation_result(order=details, scanned_at=now)
        audit_logger.info(
            "Admin order validation completed",
            extra={
                "action": "admin.order.validated",
                "actor_type": "admin",
                "actor_id": requested_by.id,
                "order_id": result.order_id,
                "validity_code": result.validity_code,
                "entry_status_code": result.entry_status_code,
            },
        )
        return result

    async def check_in_order(self, order_id: str, requested_by: UserRead) -> OrderValidationRead:
        """Mark all currently valid unchecked tickets in an order as checked in."""
        now = datetime.now(tz=timezone.utc)
        await self.session_repository.sync_completed_sessions(current_time=now, updated_at=now)

        order_document = await self.order_repository.get_by_id(order_id)
        if order_document is None:
            raise NotFoundException("Order was not found.")
        synced_orders = await self._sync_expired_reservations_for_orders([order_document], now=now)
        order_document = synced_orders[0] if synced_orders else order_document

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
        result = self._build_validation_result(order=refreshed_details, scanned_at=now)
        audit_logger.info(
            "Admin order check-in completed",
            extra={
                "action": "admin.order.checked_in",
                "actor_type": "admin",
                "actor_id": requested_by.id,
                "order_id": order_id,
                "checked_in_count": checked_in_count,
                "validity_code": result.validity_code,
                "entry_status_code": result.entry_status_code,
            },
        )
        return result

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
            refund_context = await self._build_order_refund_context(
                order_document=normalized_order,
                ticket_documents=tickets,
            )
            result.append(
                self._build_order_read(
                    order_document=normalized_order,
                    ticket_documents=tickets,
                    session_document=session.model_dump(mode="python"),
                    movie_document=movie.model_dump(mode="python"),
                    now=now,
                    refund_context=refund_context,
                )
            )
        return result

    async def _sync_expired_reservations_for_orders(
        self,
        order_documents: list[dict[str, object]],
        *,
        now: datetime,
    ) -> list[dict[str, object]]:
        """Release elapsed reservations for the sessions touched by these orders."""
        if not order_documents:
            return []

        session_ids = sorted({str(order["session_id"]) for order in order_documents})
        expired_count = 0
        for session_id in session_ids:
            expired_count += await sync_expired_reservations_for_session(
                session_id,
                now=now,
                order_repository=self.order_repository,
                ticket_repository=self.ticket_repository,
                session_repository=self.session_repository,
                payment_repository=self.payment_repository,
            )
        if expired_count <= 0:
            return order_documents

        order_ids = [str(order["id"]) for order in order_documents]
        refreshed_orders = await self.order_repository.list_by_ids(order_ids)
        refreshed_map = {str(order["id"]): order for order in refreshed_orders}
        return [refreshed_map.get(str(order["id"]), order) for order in order_documents]

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

    async def _build_order_refund_context(
        self,
        *,
        order_document: dict[str, object],
        ticket_documents: list[dict[str, object]],
    ) -> dict[str, object]:
        """Build customer-safe refund summary data for an order response."""
        if self.payment_repository is None:
            return {}

        order_id = str(order_document["id"])
        payments = await self.payment_repository.list_by_order(order_id)
        if not payments:
            return {}

        latest_payment = payments[0]
        refundable_payment = next(
            (
                payment
                for payment in payments
                if payment["status"] in ORDER_REFUNDABLE_PAYMENT_STATUSES
            ),
            None,
        )
        aggregate_payment = refundable_payment or latest_payment

        refunds = await self.refund_service.list_order_refunds(order_id) if self.refund_service is not None else []
        refunds_for_payment = [
            refund for refund in refunds if refund.payment_id == str(aggregate_payment["id"])
        ]
        refunded_amount = sum(
            refund.amount_minor
            for refund in refunds_for_payment
            if refund.status == RefundStatuses.SUCCEEDED
        )
        reserved_amount = sum(
            refund.amount_minor
            for refund in refunds_for_payment
            if refund.status in ORDER_REFUND_RESERVED_STATUSES
        )
        remaining_refundable_amount = (
            max(int(aggregate_payment["amount_minor"]) - reserved_amount, 0)
            if aggregate_payment["status"] in ORDER_REFUNDABLE_PAYMENT_STATUSES
            else 0
        )
        ticket_refunds = self._build_ticket_refund_contexts(
            ticket_documents=ticket_documents,
            refunds=refunds_for_payment,
            remaining_refundable_amount=remaining_refundable_amount,
            payment_refundable=bool(
                aggregate_payment.get("provider_payment_id")
                and aggregate_payment["status"] in ORDER_REFUNDABLE_PAYMENT_STATUSES
            ),
        )
        has_active_purchased_ticket = any(
            ticket["status"] == TicketStatuses.PURCHASED
            for ticket in ticket_documents
        )
        has_refundable_cancelled_ticket = any(
            bool(context.get("is_refundable"))
            for context in ticket_refunds.values()
        )

        return {
            "payment_id": str(aggregate_payment["id"]),
            "payment_status": str(aggregate_payment["status"]),
            "refunds_count": len(refunds_for_payment),
            "refunded_amount_minor": refunded_amount,
            "remaining_refundable_amount_minor": remaining_refundable_amount,
            "latest_refund_status": refunds_for_payment[0].status if refunds_for_payment else None,
            "full_refund_available": bool(
                aggregate_payment.get("provider_payment_id")
                and aggregate_payment["status"] in ORDER_REFUNDABLE_PAYMENT_STATUSES
                and remaining_refundable_amount > 0
                and not has_active_purchased_ticket
                and has_refundable_cancelled_ticket
            ),
            "tickets": ticket_refunds,
        }

    def _build_ticket_refund_contexts(
        self,
        *,
        ticket_documents: list[dict[str, object]],
        refunds: list[object],
        remaining_refundable_amount: int,
        payment_refundable: bool,
    ) -> dict[str, dict[str, object]]:
        """Return per-ticket refund status and eligibility derived from payment refunds."""
        refunds_by_ticket: dict[str, object] = {}
        blocking_refunded_ticket_ids: set[str] = set()
        for refund in refunds:
            ticket_ids = self._extract_refund_ticket_ids(refund)
            for ticket_id in ticket_ids:
                refunds_by_ticket.setdefault(ticket_id, refund)
                if getattr(refund, "status", None) in ORDER_REFUND_RESERVED_STATUSES:
                    blocking_refunded_ticket_ids.add(ticket_id)

        contexts: dict[str, dict[str, object]] = {}
        for ticket in ticket_documents:
            ticket_id = str(ticket["id"])
            latest_refund = refunds_by_ticket.get(ticket_id)
            ticket_amount = amount_to_minor_units(ticket["price"])
            is_refundable = (
                payment_refundable
                and remaining_refundable_amount >= ticket_amount
                and ticket["status"] == TicketStatuses.CANCELLED
                and ticket.get("checked_in_at") is None
                and ticket_id not in blocking_refunded_ticket_ids
            )
            contexts[ticket_id] = {
                "is_refundable": is_refundable,
                "refund_id": getattr(latest_refund, "id", None),
                "refund_status": getattr(latest_refund, "status", None),
                "refund_amount_minor": int(getattr(latest_refund, "amount_minor", 0) or 0),
            }
        return contexts

    def _extract_refund_ticket_ids(self, refund: object) -> list[str]:
        """Extract ticket ids from customer/admin refund metadata when present."""
        snapshot = getattr(refund, "request_payload_snapshot", None)
        if not isinstance(snapshot, dict):
            return []
        metadata = snapshot.get("metadata")
        if not isinstance(metadata, dict):
            return []

        ticket_ids: list[str] = []
        raw_ticket_id = metadata.get("ticket_id")
        if isinstance(raw_ticket_id, str) and raw_ticket_id.strip():
            ticket_ids.append(raw_ticket_id.strip())
        raw_ticket_ids = metadata.get("ticket_ids")
        if isinstance(raw_ticket_ids, list):
            ticket_ids.extend(str(ticket_id).strip() for ticket_id in raw_ticket_ids if str(ticket_id).strip())
        return list(dict.fromkeys(ticket_ids))

    def _build_order_read(
        self,
        *,
        order_document: dict[str, object],
        ticket_documents: list[dict[str, object]],
        session_document: dict[str, object],
        movie_document: dict[str, object],
        now: datetime,
        refund_context: dict[str, object] | None = None,
    ) -> OrderListRead:
        """Build one enriched order DTO."""
        order = OrderRead.model_validate(order_document)
        session = SessionRead.model_validate(session_document)
        movie = MovieRead.model_validate(movie_document)
        refund_context = refund_context or {}
        ticket_refund_contexts = refund_context.get("tickets", {})
        if not isinstance(ticket_refund_contexts, dict):
            ticket_refund_contexts = {}
        tickets = [
            self._build_order_ticket(
                ticket_document=document,
                session=session,
                order_status=order.status,
                now=now,
                refund_context=ticket_refund_contexts.get(str(document["id"])),
            )
            for document in ticket_documents
        ]
        active_tickets_count = sum(1 for ticket in tickets if ticket.status == TicketStatuses.PURCHASED)
        reserved_tickets_count = sum(1 for ticket in tickets if ticket.status == TicketStatuses.RESERVED)
        cancelled_tickets_count = sum(1 for ticket in tickets if ticket.status == TicketStatuses.CANCELLED)
        expired_tickets_count = sum(1 for ticket in tickets if ticket.status == TicketStatuses.EXPIRED)
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
            poster_file_url=str(movie.poster_file_url) if movie.poster_file_url else None,
            poster_display_url=resolve_movie_poster_url(movie),
            age_rating=movie.age_rating,
            session_start_time=session.start_time,
            session_end_time=session.end_time,
            session_price=session.price,
            session_status=session.status,
            active_tickets_count=active_tickets_count,
            reserved_tickets_count=reserved_tickets_count,
            cancelled_tickets_count=cancelled_tickets_count,
            expired_tickets_count=expired_tickets_count,
            checked_in_tickets_count=checked_in_tickets_count,
            unchecked_active_tickets_count=unchecked_active_tickets_count,
            payment_id=refund_context.get("payment_id") if isinstance(refund_context.get("payment_id"), str) else None,
            payment_status=(
                refund_context.get("payment_status") if isinstance(refund_context.get("payment_status"), str) else None
            ),
            refunds_count=int(refund_context.get("refunds_count") or 0),
            refunded_amount_minor=int(refund_context.get("refunded_amount_minor") or 0),
            remaining_refundable_amount_minor=int(refund_context.get("remaining_refundable_amount_minor") or 0),
            latest_refund_status=(
                refund_context.get("latest_refund_status")
                if isinstance(refund_context.get("latest_refund_status"), str)
                else None
            ),
            full_refund_available=bool(refund_context.get("full_refund_available")),
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
        if order.status == OrderStatuses.PENDING_PAYMENT:
            return False, VALIDATION_STATE_EXPIRED, "The order is waiting for payment and is not valid for entry."
        if order.status == OrderStatuses.PAYMENT_FAILED:
            return False, "payment_failed", "Payment failed and the seat reservation was released."
        if order.status == OrderStatuses.PAYMENT_CANCELLED:
            return False, "payment_cancelled", "Payment was cancelled and the seat reservation was released."
        if order.status == OrderStatuses.EXPIRED:
            return False, VALIDATION_STATE_EXPIRED, "The pending order reservation has expired."
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
            reserved_tickets_count=order.reserved_tickets_count,
            cancelled_tickets_count=order.cancelled_tickets_count,
            expired_tickets_count=order.expired_tickets_count,
            checked_in_tickets_count=order.checked_in_tickets_count,
            unchecked_active_tickets_count=order.unchecked_active_tickets_count,
            tickets=[
                OrderValidationTicketRead(
                    id=ticket.id,
                    seat_row=ticket.seat_row,
                    seat_number=ticket.seat_number,
                    status=ticket.status,
                    reserved_at=ticket.reserved_at,
                    expires_at=ticket.expires_at,
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
        refund_context: object | None = None,
    ) -> OrderTicketRead:
        """Build one nested ticket DTO inside an order response."""
        refund_data = refund_context if isinstance(refund_context, dict) else {}
        return OrderTicketRead(
            id=str(ticket_document["id"]),
            order_id=str(ticket_document.get("order_id")) if ticket_document.get("order_id") else None,
            seat_row=int(ticket_document["seat_row"]),
            seat_number=int(ticket_document["seat_number"]),
            price=float(ticket_document["price"]),
            status=str(ticket_document["status"]),
            reserved_at=ticket_document.get("reserved_at"),
            expires_at=ticket_document.get("expires_at"),
            purchased_at=ticket_document.get("purchased_at"),
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
            is_refundable=bool(refund_data.get("is_refundable")),
            refund_status=(
                str(refund_data["refund_status"])
                if refund_data.get("refund_status") is not None
                else None
            ),
            refund_id=(
                str(refund_data["refund_id"])
                if refund_data.get("refund_id") is not None
                else None
            ),
            refund_amount_minor=int(refund_data.get("refund_amount_minor") or 0),
        )

    def _is_ticket_cancellable(
        self,
        *,
        ticket_document: dict[str, object],
        session_document: SessionRead,
        now: datetime,
    ) -> bool:
        """Return whether an order ticket can still be cancelled."""
        ticket_status = ticket_document["status"]
        expires_at = ticket_document.get("expires_at")
        if ticket_status == TicketStatuses.RESERVED and expires_at is not None and expires_at <= now:
            return False
        return (
            ticket_status in {TicketStatuses.RESERVED, TicketStatuses.PURCHASED}
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
            and order_status in {OrderStatuses.COMPLETED, OrderStatuses.PARTIALLY_CANCELLED}
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
        if validation_state == "payment_failed":
            return "Orders with failed payments cannot be checked in."
        if validation_state == "payment_cancelled":
            return "Orders with cancelled payments cannot be checked in."
        return "Order cannot be checked in."

    def _ensure_order_owner(self, *, order_document: dict[str, object], current_user: UserRead) -> None:
        """Prevent users from reading orders that do not belong to them."""
        if current_user.role != Roles.ADMIN and order_document["user_id"] != current_user.id:
            raise AuthorizationException("You can only access your own orders.")
