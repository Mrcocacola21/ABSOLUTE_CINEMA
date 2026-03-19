"""Movie-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from app.schemas.common import BaseSchema


class MovieBase(BaseSchema):
    """Shared movie fields."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    duration_minutes: int = Field(ge=1, le=600)
    poster_url: HttpUrl | None = None
    age_rating: str | None = Field(default=None, max_length=32)
    genres: list[str] = Field(default_factory=list)
    is_active: bool = True


class MovieCreate(MovieBase):
    """Payload for creating a movie."""


class MovieUpdate(BaseSchema):
    """Payload for updating a movie."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    poster_url: HttpUrl | None = None
    age_rating: str | None = Field(default=None, max_length=32)
    genres: list[str] | None = None
    is_active: bool | None = None


class MovieRead(MovieBase):
    """Movie DTO returned by the API."""

    id: str
    created_at: datetime
    updated_at: datetime | None = None
