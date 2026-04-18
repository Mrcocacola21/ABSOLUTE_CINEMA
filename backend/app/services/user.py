"""User service skeleton."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import NotFoundException, ValidationException
from app.core.constants import Roles
from app.repositories.users import UserRepository
from app.schemas.user import UserRead, UserUpdate
from app.security.hashing import password_hasher


class UserService:
    """Service exposing user read operations used by dependencies."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def get_user_by_id(self, user_id: str) -> UserRead | None:
        """Return a user profile by identifier."""
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            return None
        return self._to_user_read(user)

    async def update_current_user(self, current_user: UserRead, payload: UserUpdate) -> UserRead:
        """Update the authenticated user's profile."""
        existing_user = await self.user_repository.get_by_id(current_user.id)
        if existing_user is None:
            raise NotFoundException("User was not found.")

        updates = payload.model_dump(mode="python", exclude_none=True)
        updates.pop("current_password", None)
        if not updates:
            raise ValidationException("At least one profile field must be provided for update.")

        if "email" in updates or "password" in updates:
            current_password = payload.current_password or ""
            if not password_hasher.verify_password(current_password, existing_user["password_hash"]):
                raise ValidationException("Current password is incorrect.")

        document_updates: dict[str, object] = {}
        if "name" in updates:
            normalized_name = str(updates["name"])
            if normalized_name != str(existing_user["name"]):
                document_updates["name"] = normalized_name
        if "email" in updates:
            normalized_email = str(updates["email"]).lower()
            if normalized_email != str(existing_user["email"]).lower():
                document_updates["email"] = normalized_email
        if "password" in updates:
            new_password = str(updates["password"])
            if password_hasher.verify_password(new_password, existing_user["password_hash"]):
                raise ValidationException("New password must be different from the current password.")
            document_updates["password_hash"] = password_hasher.hash_password(new_password)

        if not document_updates:
            raise ValidationException("At least one changed profile field must be provided.")

        updated = await self.user_repository.update_user(
            current_user.id,
            updates=document_updates,
            updated_at=datetime.now(tz=timezone.utc),
        )
        if updated is None:
            raise NotFoundException("User was not found.")
        return self._to_user_read(updated)

    async def deactivate_current_user(self, current_user: UserRead) -> UserRead:
        """Soft-deactivate the authenticated user instead of deleting historical data."""
        updated = await self.user_repository.update_user(
            current_user.id,
            updates={"is_active": False},
            updated_at=datetime.now(tz=timezone.utc),
        )
        if updated is None:
            raise NotFoundException("User was not found.")
        return self._to_user_read(updated)

    async def list_users(self, requested_by: UserRead) -> list[UserRead]:
        """Return all users for admin views without sensitive fields."""
        _ = requested_by
        users = await self.user_repository.list_users()
        return [self._to_user_read(user) for user in users]

    def _to_user_read(self, user: dict[str, object]) -> UserRead:
        normalized = dict(user)
        normalized.pop("password_hash", None)
        if normalized.get("role") not in {Roles.USER, Roles.ADMIN}:
            normalized["role"] = Roles.USER
        return UserRead.model_validate(normalized)
