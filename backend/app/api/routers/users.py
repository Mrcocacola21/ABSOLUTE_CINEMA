"""User profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_user_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.user import UserRead, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserRead])
async def get_me(current_user: UserRead = Depends(get_current_user)) -> ApiResponse[UserRead]:
    """Return the profile of the authenticated user."""
    return ApiResponseFactory.success(data=current_user, message="Current user loaded.")


@router.patch("/me", response_model=ApiResponse[UserRead])
async def update_me(
    payload: UserUpdate,
    current_user: UserRead = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserRead]:
    """Update the profile of the authenticated user."""
    user = await user_service.update_current_user(current_user=current_user, payload=payload)
    return ApiResponseFactory.success(data=user, message="Profile updated successfully.")


@router.delete("/me", response_model=ApiResponse[UserRead])
async def deactivate_me(
    current_user: UserRead = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserRead]:
    """Deactivate the authenticated user account."""
    user = await user_service.deactivate_current_user(current_user=current_user)
    return ApiResponseFactory.success(data=user, message="User account deactivated successfully.")
