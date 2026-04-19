"""User-related schemas."""

from __future__ import annotations

from datetime import datetime
import re

from pydantic import ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.constants import Roles
from app.schemas.common import BaseSchema

WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_person_name(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = WHITESPACE_PATTERN.sub(" ", value).strip()
    if not normalized:
        raise ValueError("name cannot be blank.")
    return normalized


class UserCreate(BaseSchema):
    """Payload for registering a new user."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Collapse repeated whitespace in display names while preserving usability."""
        return _normalize_person_name(value) or value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Store emails in lowercase consistently across create and update flows."""
        return str(value).lower()


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

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    current_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Normalize profile names consistently for partial updates too."""
        return _normalize_person_name(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        """Lowercase optional email updates before they reach the service layer."""
        if value is None:
            return None
        return str(value).lower()

    @model_validator(mode="after")
    def validate_sensitive_changes(self) -> "UserUpdate":
        """Require the current password for email or password changes."""
        if (self.email or self.password) and not self.current_password:
            raise ValueError("current_password is required to change email or password.")
        if self.password is not None and self.password == self.current_password:
            raise ValueError("New password must be different from current_password.")
        return self
