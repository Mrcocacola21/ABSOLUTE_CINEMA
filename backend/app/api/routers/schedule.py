"""Schedule browsing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.pagination import get_pagination_params, get_schedule_query_params
from app.api.dependencies.services import get_schedule_service
from app.core.responses import ApiResponse, ResponseMeta
from app.factories.response_factory import ApiResponseFactory
from app.schemas.common import PaginationParams
from app.schemas.session import ScheduleItemRead, ScheduleQueryParams, SessionDetailsRead
from app.services.schedule import ScheduleService

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=ApiResponse[list[ScheduleItemRead]])
async def get_schedule(
    pagination: PaginationParams = Depends(get_pagination_params),
    query_params: ScheduleQueryParams = Depends(get_schedule_query_params),
    schedule_service: ScheduleService = Depends(get_schedule_service),
) -> ApiResponse[list[ScheduleItemRead]]:
    """Return the schedule with pagination, filtering, and sorting support."""
    items, pagination_meta = await schedule_service.list_schedule(
        pagination=pagination,
        filters=query_params,
    )
    meta = ResponseMeta(pagination=pagination_meta)
    return ApiResponseFactory.success(data=items, message="Schedule loaded.", meta=meta)


@router.get("/{session_id}", response_model=ApiResponse[SessionDetailsRead])
async def get_session_details(
    session_id: str,
    schedule_service: ScheduleService = Depends(get_schedule_service),
) -> ApiResponse[SessionDetailsRead]:
    """Return details for a specific scheduled session."""
    session = await schedule_service.get_session_details(session_id)
    return ApiResponseFactory.success(data=session, message="Session details loaded.")
