"""Authentication and authorization dependencies."""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.api.dependencies.services import get_user_service
from app.core.config import get_settings
from app.core.constants import Roles
from app.core.exceptions import AuthenticationException, AuthorizationException, ValidationException
from app.schemas.user import UserRead
from app.security.jwt import decode_access_token
from app.services.user import UserService

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/token",
    auto_error=False,
    description=(
        "Use Swagger's Authorize button to exchange email and password for an access JWT, "
        "or call POST /api/v1/auth/login and paste `data.access_token` manually. "
        "Call POST /api/v1/auth/refresh with `data.refresh_token` when an access token expires."
    ),
)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> UserRead:
    """Resolve the authenticated user from the provided bearer token."""
    if not token:
        raise AuthenticationException("Authentication is required to access this resource.")

    payload = decode_access_token(token)
    user_id = payload.sub
    if not user_id:
        raise AuthenticationException("Invalid or expired access token.")

    try:
        user = await user_service.get_user_by_id(user_id)
    except ValidationException as exc:
        raise AuthenticationException("Invalid or expired access token.") from exc

    if not user:
        raise AuthenticationException("Authenticated user no longer exists.")
    if not user.is_active:
        raise AuthenticationException("This account is inactive.")
    return user


async def get_current_admin(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    """Ensure that the authenticated user has administrator privileges."""
    if current_user.role != Roles.ADMIN:
        raise AuthorizationException("Administrator role is required.")
    return current_user


async def get_current_customer(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    """Ensure that the authenticated user is using customer self-service routes as a customer."""
    if current_user.role == Roles.ADMIN:
        raise AuthorizationException("Customer self-service routes are not available to administrator accounts.")
    return current_user
