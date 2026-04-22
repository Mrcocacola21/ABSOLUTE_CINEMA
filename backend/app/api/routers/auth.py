"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.docs import (
    AUTHENTICATION_ERROR_RESPONSE,
    CONFLICT_ERROR_RESPONSE,
    REQUEST_VALIDATION_ERROR_RESPONSE,
    merge_openapi_responses,
)
from app.api.dependencies.services import get_auth_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.auth import TokenRead
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

RegisterPayload = Annotated[
    UserCreate,
    Body(
        openapi_examples={
            "customer_registration": {
                "summary": "Standard customer registration",
                "value": {
                    "name": "Olena Kovalenko",
                    "email": "olena@example.com",
                    "password": "CinemaPass123",
                },
            }
        }
    ),
]


@router.post(
    "/register",
    response_model=ApiResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a customer account for sign-in, ticket purchases, and the frontend profile area. "
        "Roles are assigned server-side; clients cannot self-register as administrators."
    ),
    response_description="Wrapped public user profile without password hash or raw password fields.",
    responses=merge_openapi_responses(CONFLICT_ERROR_RESPONSE, REQUEST_VALIDATION_ERROR_RESPONSE),
)
async def register(
    payload: RegisterPayload,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[UserRead]:
    """Register a new user account."""
    user = await auth_service.register_user(payload)
    return ApiResponseFactory.created(data=user, message="Registration completed successfully.")


@router.post(
    "/login",
    response_model=ApiResponse[TokenRead],
    summary="Log in and receive a JWT",
    description=(
        "Authenticate with form-encoded credentials. This app-facing endpoint returns the standard "
        "API response envelope with a JWT access token in `data.access_token`."
    ),
    response_description="Wrapped JWT token payload for the frontend and API clients.",
    responses=merge_openapi_responses(AUTHENTICATION_ERROR_RESPONSE, REQUEST_VALIDATION_ERROR_RESPONSE),
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[TokenRead]:
    """Authenticate a user using the OAuth2 password flow."""
    token = await auth_service.login_user(
        username=form_data.username,
        password=form_data.password,
    )
    return ApiResponseFactory.success(data=token, message="Login successful.")


@router.post(
    "/token",
    response_model=TokenRead,
    include_in_schema=False,
)
async def issue_swagger_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenRead:
    """OAuth2-compatible token exchange used by Swagger UI authorization."""
    return await auth_service.login_user(
        username=form_data.username,
        password=form_data.password,
    )
