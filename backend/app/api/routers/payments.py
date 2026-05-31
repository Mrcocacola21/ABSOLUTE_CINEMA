"""Payment initiation and inspection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, Request, status

from app.api.dependencies.auth import get_current_admin, get_current_customer, get_current_user
from app.api.dependencies.services import get_payment_service
from app.api.docs import (
    AUTHENTICATION_ERROR_RESPONSE,
    AUTHORIZATION_ERROR_RESPONSE,
    CONFLICT_ERROR_RESPONSE,
    NOT_FOUND_ERROR_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
    merge_openapi_responses,
)
from app.core.exceptions import AuthorizationException, ConflictException
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.payment import (
    CustomerRefundRead,
    CustomerRefundRequest,
    PaymentDetailsRead,
    PaymentInitiationRead,
    PaymentInitiationRequest,
    PaymentSimulationRead,
    PaymentSimulationRequest,
    PaymentWebhookProcessingRead,
    RefundRead,
    RefundRequest,
)
from app.schemas.user import UserRead
from app.services.payment import PaymentService

router = APIRouter(tags=["payments"], responses=AUTHENTICATION_ERROR_RESPONSE)


@router.post(
    "/orders/{order_id}/payments",
    response_model=ApiResponse[PaymentInitiationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate order payment",
    description=(
        "Create or reuse a provider-neutral payment for a pending order, record a payment attempt, "
        "call the configured payment provider adapter, and return only normalized checkout data. "
        "A later provider webhook is responsible for finalizing the local order and ticket entitlements. "
        "If the order reservation has expired, this endpoint releases the hold first and rejects payment initiation."
    ),
    response_description="Wrapped provider-neutral payment initiation result.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def initiate_order_payment(
    order_id: str,
    payload: PaymentInitiationRequest = Body(default_factory=PaymentInitiationRequest),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional request idempotency key for safe client retries.",
    ),
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[PaymentInitiationRead]:
    """Initiate checkout for a pending order owned by the current user."""
    if idempotency_key and payload.idempotency_key and idempotency_key.strip() != payload.idempotency_key.strip():
        raise ConflictException("Conflicting idempotency keys were provided.")

    initiation = await payment_service.initiate_order_payment(
        order_id=order_id,
        current_user=current_user,
        idempotency_key=idempotency_key or payload.idempotency_key,
        metadata=payload.metadata,
        return_url=payload.return_url,
        cancel_url=payload.cancel_url,
    )
    return ApiResponseFactory.created(data=initiation, message="Payment initiation prepared.")


@router.post(
    "/orders/{order_id}/payments/retry",
    response_model=ApiResponse[PaymentInitiationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Retry order payment",
    description=(
        "Create a new provider-neutral payment for the same pending order after a previous local payment "
        "failed, was cancelled, or expired. Retry is accepted only while the seat reservation is still active; "
        "completed, cancelled, expired, or already-released orders cannot re-enter checkout."
    ),
    response_description="Wrapped provider-neutral payment retry initiation result.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def retry_order_payment(
    order_id: str,
    payload: PaymentInitiationRequest = Body(default_factory=PaymentInitiationRequest),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional retry idempotency key for safe client retries.",
    ),
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[PaymentInitiationRead]:
    """Retry checkout for an active reservation after a non-success payment."""
    if idempotency_key and payload.idempotency_key and idempotency_key.strip() != payload.idempotency_key.strip():
        raise ConflictException("Conflicting idempotency keys were provided.")

    initiation = await payment_service.retry_order_payment(
        order_id=order_id,
        current_user=current_user,
        idempotency_key=idempotency_key or payload.idempotency_key,
        metadata=payload.metadata,
        return_url=payload.return_url,
        cancel_url=payload.cancel_url,
    )
    return ApiResponseFactory.created(data=initiation, message="Payment retry prepared.")


@router.get(
    "/payments/{payment_id}",
    response_model=ApiResponse[PaymentDetailsRead],
    summary="Get payment details",
    description=(
        "Return a safe provider-neutral payment aggregate and its recorded attempt history. "
        "Provider raw SDK objects and sensitive payment data are never exposed. "
        "If the linked pending reservation has timed out, active local payments are synchronized to `expired` first."
    ),
    response_description="Wrapped payment details with safe attempt history.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def get_payment_details(
    payment_id: str,
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[PaymentDetailsRead]:
    """Return one accessible payment and its attempt history."""
    payment = await payment_service.get_payment_details(payment_id, current_user=current_user)
    return ApiResponseFactory.success(data=payment, message="Payment loaded.")


@router.get(
    "/orders/{order_id}/payment",
    response_model=ApiResponse[PaymentDetailsRead],
    summary="Get latest order payment",
    description=(
        "Return the latest provider-neutral payment recorded for an accessible order. "
        "Use this for checkout/status screens without exposing raw provider SDK payloads. "
        "Pending, failed, cancelled, and expired states are returned explicitly for checkout recovery screens."
    ),
    response_description="Wrapped latest order payment details.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def get_order_payment_details(
    order_id: str,
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[PaymentDetailsRead]:
    """Return the latest payment for an accessible order."""
    payment = await payment_service.get_order_payment_details(order_id, current_user=current_user)
    return ApiResponseFactory.success(data=payment, message="Order payment loaded.")


@router.post(
    "/payments/{payment_id}/simulate",
    response_model=ApiResponse[PaymentSimulationRead],
    summary="Simulate fake-provider payment result",
    description=(
        "Development/demo-only endpoint for the local fake payment page. The endpoint is guarded to the configured "
        "fake provider in a non-production environment, requires the authenticated payment owner or an administrator, "
        "builds a signed fake-provider webhook, and sends it through the same webhook processor that finalizes paid "
        "orders or releases failed/cancelled reservations. `pending` emits a fake-provider pending event and keeps "
        "the payment unresolved."
    ),
    response_description="Wrapped simulation result with refreshed payment details and webhook processing state.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def simulate_fake_provider_payment(
    payment_id: str,
    payload: PaymentSimulationRequest,
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[PaymentSimulationRead]:
    """Drive a demo fake-provider result through the real webhook finalization path."""
    simulation = await payment_service.simulate_fake_provider_payment(
        payment_id,
        result=payload.result,
        current_user=current_user,
    )
    return ApiResponseFactory.success(data=simulation, message="Fake payment simulation processed.")


@router.post(
    "/payments/{payment_id}/refunds",
    response_model=ApiResponse[RefundRead],
    status_code=status.HTTP_201_CREATED,
    summary="Legacy payment refund route",
    description=(
        "Legacy route kept for compatibility discovery only. Administrator financial refunds must be created "
        "through `/admin/payments/{payment_id}/refunds` so the action happens in the explicit admin context."
    ),
    response_description="Wrapped refund record after provider-normalized processing.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def create_payment_refund(
    payment_id: str,
    payload: RefundRequest,
    current_admin: UserRead = Depends(get_current_admin),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[RefundRead]:
    """Reject legacy non-admin-path refund creation."""
    _ = (payment_id, payload, current_admin, payment_service)
    raise AuthorizationException("Use the admin payment refund endpoint for administrator refund actions.")


@router.post(
    "/orders/{order_id}/refunds/request",
    response_model=ApiResponse[CustomerRefundRead],
    status_code=status.HTTP_201_CREATED,
    summary="Request customer order refund",
    description=(
        "Create a customer-facing refund request without moving money outside the payment subsystem. "
        "`scope=tickets` computes a partial refund from the selected cancelled ticket ids and creates a refund "
        "against the order payment. `scope=order` refunds the remaining refundable payment amount only after the "
        "order has no active purchased tickets. Customer self-service refund requests are limited to the "
        "authenticated customer's own orders. Administrator refunds are exposed separately under the `admin` tag."
    ),
    response_description="Wrapped refund record with refreshed payment and order refund history.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def request_customer_order_refund(
    order_id: str,
    payload: CustomerRefundRequest,
    current_user: UserRead = Depends(get_current_customer),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[CustomerRefundRead]:
    """Request a customer refund while preserving payment/order financial ownership."""
    refund = await payment_service.request_order_refund(
        order_id=order_id,
        payload=payload,
        current_user=current_user,
    )
    return ApiResponseFactory.created(data=refund, message="Refund request created.")


@router.get(
    "/payments/{payment_id}/refunds",
    response_model=ApiResponse[list[RefundRead]],
    summary="List payment refunds",
    description=(
        "Return refund history for an accessible payment. Refund records expose normalized financial state and "
        "safe provider references, not raw provider payloads or secrets."
    ),
    response_description="Wrapped refund history for the payment.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def list_payment_refunds(
    payment_id: str,
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[list[RefundRead]]:
    """Return refund history for one accessible payment."""
    refunds = await payment_service.list_payment_refunds(payment_id, current_user=current_user)
    return ApiResponseFactory.success(data=refunds, message="Payment refunds loaded.")


@router.get(
    "/orders/{order_id}/refunds",
    response_model=ApiResponse[list[RefundRead]],
    summary="List order refunds",
    description=(
        "Return refund history for an accessible order. Use this to show whether a booking cancellation has an "
        "associated pending, succeeded, failed, or cancelled financial refund."
    ),
    response_description="Wrapped refund history for the order.",
    responses=merge_openapi_responses(
        AUTHORIZATION_ERROR_RESPONSE,
        NOT_FOUND_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def list_order_refunds(
    order_id: str,
    current_user: UserRead = Depends(get_current_user),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[list[RefundRead]]:
    """Return refund history for one accessible order."""
    refunds = await payment_service.list_order_refunds(order_id, current_user=current_user)
    return ApiResponseFactory.success(data=refunds, message="Order refunds loaded.")


@router.post(
    "/payments/webhook",
    response_model=ApiResponse[PaymentWebhookProcessingRead],
    summary="Receive payment provider webhook",
    description=(
        "Receive a raw payment provider webhook, verify its signature with the configured provider adapter, "
        "persist an audit record, deduplicate by provider event id, update local payment state, and finalize or "
        "release the pending order reservation when payment fails, is cancelled, or expires. This endpoint is provider-neutral and does not "
        "require bearer authentication because authenticity is established by webhook signature verification."
    ),
    response_description="Wrapped webhook processing acknowledgment.",
    responses=merge_openapi_responses(
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def receive_payment_webhook(
    request: Request,
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse[PaymentWebhookProcessingRead]:
    """Process a signed provider webhook event."""
    raw_body = await request.body()
    result = await payment_service.process_provider_webhook(
        raw_body=raw_body,
        headers=dict(request.headers),
    )
    return ApiResponseFactory.success(data=result, message="Payment webhook processed.")
