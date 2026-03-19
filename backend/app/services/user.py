"""User service skeleton."""

from __future__ import annotations

from app.repositories.users import UserRepository
from app.schemas.user import UserRead


class UserService:
    """Service exposing user read operations used by dependencies."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def get_user_by_id(self, user_id: str) -> UserRead | None:
        """Return a user profile by identifier."""
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            return None
        user.pop("password_hash", None)
        return UserRead.model_validate(user)
