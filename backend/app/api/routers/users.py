"""User profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserRead])
async def get_me(current_user: UserRead = Depends(get_current_user)) -> ApiResponse[UserRead]:
    """Return the profile of the authenticated user."""
    return ApiResponseFactory.success(data=current_user, message="Current user loaded.")
