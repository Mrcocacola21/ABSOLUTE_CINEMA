"""Order purchase endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_order_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.order import OrderDetailsRead, OrderPurchaseRequest
from app.schemas.user import UserRead
from app.services.order import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/purchase", response_model=ApiResponse[OrderDetailsRead], status_code=status.HTTP_201_CREATED)
async def purchase_order(
    payload: OrderPurchaseRequest,
    current_user: UserRead = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse[OrderDetailsRead]:
    """Purchase one or more seats for the same session as one order."""
    order = await order_service.purchase_order(payload=payload, current_user=current_user)
    return ApiResponseFactory.created(data=order, message="Order purchased successfully.")


@router.patch("/{order_id}/cancel", response_model=ApiResponse[OrderDetailsRead])
async def cancel_order(
    order_id: str,
    current_user: UserRead = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse[OrderDetailsRead]:
    """Cancel all active tickets in one order."""
    order = await order_service.cancel_order(order_id=order_id, current_user=current_user)
    return ApiResponseFactory.success(data=order, message="Order cancelled successfully.")
