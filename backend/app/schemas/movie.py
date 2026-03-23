"""Movie-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl, field_validator

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

    @field_validator("genres")
    @classmethod
    def normalize_genres(cls, value: list[str]) -> list[str]:
        """Trim, deduplicate, and drop blank genre values."""
        normalized: list[str] = []
        seen: set[str] = set()

        for genre in value:
            cleaned = genre.strip()
            if not cleaned:
                continue
            normalized_key = cleaned.lower()
            if normalized_key in seen:
                continue
            seen.add(normalized_key)
            normalized.append(cleaned)
        return normalized


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

    @field_validator("genres")
    @classmethod
    def normalize_genres(cls, value: list[str] | None) -> list[str] | None:
        """Trim, deduplicate, and drop blank genre values for partial updates too."""
        if value is None:
            return None
        return MovieBase.normalize_genres(value)


class MovieRead(MovieBase):
    """Movie DTO returned by the API."""

    id: str
    created_at: datetime
    updated_at: datetime | None = None
