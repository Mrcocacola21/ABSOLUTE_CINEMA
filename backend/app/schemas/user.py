"""User-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.core.constants import Roles
from app.schemas.common import BaseSchema


class UserCreate(BaseSchema):
    """Payload for registering a new user."""

    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseSchema):
    """User DTO returned by the API."""

    id: str
    name: str
    email: EmailStr
    role: str = Roles.USER
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class UserUpdate(BaseSchema):
    """Payload for updating the authenticated user's profile."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    current_password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_sensitive_changes(self) -> "UserUpdate":
        """Require the current password for email or password changes."""
        if (self.email or self.password) and not self.current_password:
            raise ValueError("current_password is required to change email or password.")
        return self
