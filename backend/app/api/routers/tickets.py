"""Ticket purchase endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_ticket_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.ticket import TicketPurchaseRequest, TicketRead
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
