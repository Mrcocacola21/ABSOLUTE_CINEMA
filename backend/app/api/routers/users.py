"""User profile endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.api.dependencies.auth import get_current_user
from app.api.docs import (
    AUTHENTICATION_ERROR_RESPONSE,
    CONFLICT_ERROR_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
    merge_openapi_responses,
)
from app.api.dependencies.services import get_order_service, get_user_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.order import OrderDetailsRead, OrderListRead
from app.schemas.user import UserRead, UserUpdate
from app.services.order import OrderService
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"], responses=AUTHENTICATION_ERROR_RESPONSE)

ProfileUpdatePayload = Annotated[
    UserUpdate,
    Body(
        openapi_examples={
            "display_name_only": {
                "summary": "Update only the display name",
                "value": {
                    "name": "Updated Cinema Guest",
                },
            },
            "email_change": {
                "summary": "Change the email address",
                "value": {
                    "email": "updated@example.com",
                    "current_password": "CinemaPass123",
                },
            },
            "password_change": {
                "summary": "Change the password",
                "value": {
                    "password": "NewCinemaPass123",
                    "current_password": "CinemaPass123",
                },
            },
        }
    ),
]


@router.get(
    "/me",
    response_model=ApiResponse[UserRead],
    summary="Restore the current user session",
    description=(
        "Resolve the authenticated user from the bearer token and return the safe public profile "
        "used by the frontend to restore an existing session."
    ),
    response_description="Wrapped authenticated user profile.",
)
async def get_me(current_user: UserRead = Depends(get_current_user)) -> ApiResponse[UserRead]:
    """Return the profile of the authenticated user."""
    return ApiResponseFactory.success(data=current_user, message="Current user loaded.")


@router.get(
    "/me/orders",
    response_model=ApiResponse[list[OrderListRead]],
    summary="List my orders",
    description="Return all grouped orders that belong to the authenticated user.",
    response_description="Wrapped list of the current user's orders.",
)
async def list_my_orders(
    current_user: UserRead = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse[list[OrderListRead]]:
    """Return grouped orders belonging to the authenticated user."""
    orders = await order_service.list_current_user_orders(current_user=current_user)
    return ApiResponseFactory.success(data=orders, message="Orders loaded.")


@router.get(
    "/me/orders/{order_id}",
    response_model=ApiResponse[OrderDetailsRead],
    summary="Get one of my orders",
    description="Return one grouped order owned by the authenticated user.",
    response_description="Wrapped order details for a single order.",
)
async def get_my_order(
    order_id: str,
    current_user: UserRead = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse[OrderDetailsRead]:
    """Return one grouped order belonging to the authenticated user."""
    order = await order_service.get_current_user_order(order_id=order_id, current_user=current_user)
    return ApiResponseFactory.success(data=order, message="Order loaded.")


@router.patch(
    "/me",
    response_model=ApiResponse[UserRead],
    summary="Edit the current profile",
    description=(
        "Update the authenticated user's profile. Changing the email or password requires "
        "`current_password`; role and activation flags cannot be changed through this endpoint."
    ),
    response_description="Wrapped updated user profile.",
    responses=merge_openapi_responses(CONFLICT_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def update_me(
    payload: ProfileUpdatePayload,
    current_user: UserRead = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserRead]:
    """Update the profile of the authenticated user."""
    user = await user_service.update_current_user(current_user=current_user, payload=payload)
    return ApiResponseFactory.success(data=user, message="Profile updated successfully.")


@router.delete(
    "/me",
    response_model=ApiResponse[UserRead],
    summary="Deactivate the current account",
    description=(
        "Soft-deactivate the authenticated account. Existing tokens stop working after deactivation, "
        "and future login attempts are rejected for that account."
    ),
    response_description="Wrapped user profile after deactivation.",
)
async def deactivate_me(
    current_user: UserRead = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserRead]:
    """Deactivate the authenticated user account."""
    user = await user_service.deactivate_current_user(current_user=current_user)
    return ApiResponseFactory.success(data=user, message="User account deactivated successfully.")
