"""Ticket service skeleton."""

from __future__ import annotations

from app.commands.ticket_purchase import TicketPurchaseCommand
from app.observers.events import build_default_event_publisher
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.schemas.ticket import TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead


class TicketService:
    """Service encapsulating ticket-related use cases."""

    def __init__(
        self,
        session_repository: SessionRepository,
        ticket_repository: TicketRepository,
    ) -> None:
        self.session_repository = session_repository
        self.ticket_repository = ticket_repository
        self.event_publisher = build_default_event_publisher()

    async def purchase_ticket(self, payload: TicketPurchaseRequest, current_user: UserRead) -> TicketRead:
        """Purchase a ticket via a command object."""
        command = TicketPurchaseCommand(
            session_repository=self.session_repository,
            ticket_repository=self.ticket_repository,
            event_publisher=self.event_publisher,
        )
        return await command.execute(payload=payload, current_user=current_user)
