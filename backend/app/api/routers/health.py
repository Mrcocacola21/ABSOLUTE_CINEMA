"""Health-check endpoints."""

from fastapi import APIRouter

from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
async def health_check() -> ApiResponse[dict[str, str]]:
    """Provide a simple backend liveness response."""
    return ApiResponseFactory.success(
        data={"status": "ok"},
        message="Cinema Showcase backend is healthy.",
    )
