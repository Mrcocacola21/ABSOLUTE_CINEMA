"""Session-specific endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.services import get_schedule_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.session import SessionSeatsRead
from app.services.schedule import ScheduleService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}/seats", response_model=ApiResponse[SessionSeatsRead])
async def get_session_seats(
    session_id: str,
    schedule_service: ScheduleService = Depends(get_schedule_service),
) -> ApiResponse[SessionSeatsRead]:
    """Return seat availability for a specific session."""
    seats = await schedule_service.get_session_seats(session_id)
    return ApiResponseFactory.success(data=seats, message="Seat availability loaded.")
