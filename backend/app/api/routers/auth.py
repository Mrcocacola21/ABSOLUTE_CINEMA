"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies.services import get_auth_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.auth import TokenRead
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiResponse[UserRead], status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[UserRead]:
    """Register a new user account."""
    user = await auth_service.register_user(payload)
    return ApiResponseFactory.created(data=user, message="Registration completed successfully.")


@router.post("/login", response_model=ApiResponse[TokenRead])
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
