"""Authentication service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.constants import Roles
from app.core.exceptions import AuthenticationException, ConflictException
from app.repositories.users import UserRepository
from app.schemas.auth import TokenRead
from app.schemas.user import UserCreate, UserRead
from app.security.hashing import password_hasher
from app.security.jwt import create_access_token


class AuthService:
    """Service encapsulating user registration and login workflows."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def register_user(self, payload: UserCreate) -> UserRead:
        """Create a new user account if the email is still available."""
        existing_user = await self.user_repository.get_by_email(payload.email)
        if existing_user:
            raise ConflictException("A user with this email already exists.")

        settings = get_settings()
        normalized_email = payload.email.lower()
        admin_emails = {email.lower() for email in settings.admin_emails}
        now = datetime.now(tz=timezone.utc)
        document = {
            "name": payload.name,
            "email": normalized_email,
            "password_hash": password_hasher.hash_password(payload.password),
            "role": Roles.ADMIN if normalized_email in admin_emails else Roles.USER,
            "is_active": True,
            "created_at": now,
            "updated_at": None,
        }

        created_user = await self.user_repository.create_user(document)
        created_user.pop("password_hash", None)
        return UserRead.model_validate(created_user)

    async def login_user(self, username: str, password: str) -> TokenRead:
        """Authenticate a user and issue a JWT access token."""
        user = await self.user_repository.get_by_email(username)
        if not user:
            raise AuthenticationException("Incorrect email or password.")
        if not user["is_active"]:
            raise AuthenticationException("This account is inactive.")
        if not password_hasher.verify_password(password, user["password_hash"]):
            raise AuthenticationException("Incorrect email or password.")

        access_token, expires_in = create_access_token(
            subject=user["id"],
            email=user["email"],
            role=user["role"],
        )
        return TokenRead(
            access_token=access_token,
            expires_in=expires_in,
        )
