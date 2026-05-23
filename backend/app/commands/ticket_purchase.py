"""Command handling legacy single-ticket reservation workflow."""

from __future__ import annotations

from app.commands.order_purchase import OrderPurchaseCommand
from app.observers.events import EventPublisher
from app.repositories.orders import OrderRepository
from app.repositories.payments import PaymentRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.order import OrderPurchaseRequest, OrderSeatInput
from app.schemas.ticket import TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead


class TicketPurchaseCommand:
    """Encapsulate the single-ticket pending reservation use case."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        order_repository: OrderRepository,
        event_publisher: EventPublisher,
        payment_repository: PaymentRepository | None = None,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.order_repository = order_repository
        self.event_publisher = event_publisher
        self.payment_repository = payment_repository

    async def execute(self, payload: TicketPurchaseRequest, current_user: UserRead) -> TicketRead:
        """Reserve one seat by delegating to the order-aware bulk reservation command."""
        order_purchase = OrderPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
            event_publisher=self.event_publisher,
            payment_repository=self.payment_repository,
        )
        result = await order_purchase.execute(
            payload=OrderPurchaseRequest(
                session_id=payload.session_id,
                seats=[
                    OrderSeatInput(
                        seat_row=payload.seat_row,
                        seat_number=payload.seat_number,
                    )
                ],
            ),
            current_user=current_user,
        )
        return TicketRead.model_validate(result["tickets"][0])
