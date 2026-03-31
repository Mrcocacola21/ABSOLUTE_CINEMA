"""User profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_order_service, get_user_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.order import OrderDetailsRead, OrderListRead
from app.schemas.user import UserRead, UserUpdate
from app.services.order import OrderService
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserRead])
async def get_me(current_user: UserRead = Depends(get_current_user)) -> ApiResponse[UserRead]:
    """Return the profile of the authenticated user."""
    return ApiResponseFactory.success(data=current_user, message="Current user loaded.")


@router.get("/me/orders", response_model=ApiResponse[list[OrderListRead]])
async def list_my_orders(
    current_user: UserRead = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse[list[OrderListRead]]:
    """Return grouped orders belonging to the authenticated user."""
    orders = await order_service.list_current_user_orders(current_user=current_user)
    return ApiResponseFactory.success(data=orders, message="Orders loaded.")


@router.get("/me/orders/{order_id}", response_model=ApiResponse[OrderDetailsRead])
async def get_my_order(
    order_id: str,
    current_user: UserRead = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse[OrderDetailsRead]:
    """Return one grouped order belonging to the authenticated user."""
    order = await order_service.get_current_user_order(order_id=order_id, current_user=current_user)
    return ApiResponseFactory.success(data=order, message="Order loaded.")


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
