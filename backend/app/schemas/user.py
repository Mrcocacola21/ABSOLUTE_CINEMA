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
        json_schema_extra={
            "example": {
                "name": "Olena Kovalenko",
                "email": "olena@example.com",
                "password": "CinemaPass123",
            }
        },
    )

    name: str = Field(min_length=2, max_length=255, description="Display name shown in the profile area.")
    email: EmailStr = Field(description="Unique user email used for sign-in.")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Plain-text password accepted during registration before server-side hashing.",
    )

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
    role: str = Field(
        default=Roles.USER,
        description="User role assigned by the backend.",
        json_schema_extra={"enum": [Roles.USER, Roles.ADMIN]},
    )
    is_active: bool = Field(
        default=True,
        description="Whether the account can still authenticate and access protected endpoints.",
    )
    created_at: datetime
    updated_at: datetime | None = None


class UserUpdate(BaseSchema):
    """Payload for updating the authenticated user's profile."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {"name": "Updated Cinema Guest"},
                {"email": "updated@example.com", "current_password": "CinemaPass123"},
                {"password": "NewCinemaPass123", "current_password": "CinemaPass123"},
            ]
        },
    )

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Optional new display name.",
    )
    email: EmailStr | None = Field(
        default=None,
        description="Optional new email address. Requires `current_password`.",
    )
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Optional new password. Requires `current_password`.",
    )
    current_password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Current password used to authorize email or password changes.",
    )

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
