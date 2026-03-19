"""User-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

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
