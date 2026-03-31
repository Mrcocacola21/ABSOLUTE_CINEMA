"""Command handling legacy single-ticket purchase workflow."""

from __future__ import annotations

from app.commands.order_purchase import OrderPurchaseCommand
from app.observers.events import EventPublisher
from app.repositories.orders import OrderRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.order import OrderPurchaseRequest, OrderSeatInput
from app.schemas.ticket import TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead


class TicketPurchaseCommand:
    """Encapsulate the ticket purchasing use case."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
        order_repository: OrderRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.order_repository = order_repository
        self.event_publisher = event_publisher

    async def execute(self, payload: TicketPurchaseRequest, current_user: UserRead) -> TicketRead:
        """Purchase one seat by delegating to the order-aware bulk purchase command."""
        order_purchase = OrderPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            order_repository=self.order_repository,
            event_publisher=self.event_publisher,
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
