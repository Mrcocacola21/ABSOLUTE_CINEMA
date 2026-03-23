"""Ticket purchase endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_ticket_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.ticket import TicketListRead, TicketPurchaseRequest, TicketRead
from app.schemas.user import UserRead
from app.services.ticket import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/purchase", response_model=ApiResponse[TicketRead], status_code=status.HTTP_201_CREATED)
async def purchase_ticket(
    payload: TicketPurchaseRequest,
    current_user: UserRead = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> ApiResponse[TicketRead]:
    """Purchase a ticket for a selected session."""
    ticket = await ticket_service.purchase_ticket(payload=payload, current_user=current_user)
    return ApiResponseFactory.created(data=ticket, message="Ticket purchased successfully.")


@router.get("/me", response_model=ApiResponse[list[TicketListRead]])
async def list_current_user_tickets(
    current_user: UserRead = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> ApiResponse[list[TicketListRead]]:
    """Return tickets belonging to the authenticated user."""
    tickets = await ticket_service.list_current_user_tickets(current_user=current_user)
    return ApiResponseFactory.success(data=tickets, message="Tickets loaded.")


@router.patch("/{ticket_id}/cancel", response_model=ApiResponse[TicketRead])
async def cancel_ticket(
    ticket_id: str,
    current_user: UserRead = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> ApiResponse[TicketRead]:
    """Cancel a ticket owned by the current user or by any user when performed by an admin."""
    ticket = await ticket_service.cancel_ticket(ticket_id=ticket_id, current_user=current_user)
    return ApiResponseFactory.success(data=ticket, message="Ticket cancelled successfully.")
