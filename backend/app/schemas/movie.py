"""Movie-related schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.core.constants import MOVIE_STATUS_VALUES, MovieStatuses
from app.schemas.common import BaseSchema


def _populate_legacy_movie_status(value: Any) -> Any:
    """Map legacy boolean flags into the explicit movie status field."""
    if not isinstance(value, dict):
        return value

    if "status" in value or "is_active" not in value:
        return value

    return {
        **value,
        "status": MovieStatuses.ACTIVE if value.get("is_active") else MovieStatuses.DEACTIVATED,
    }


class MovieBase(BaseSchema):
    """Shared movie fields."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    duration_minutes: int = Field(ge=1, le=600)
    poster_url: HttpUrl | None = None
    age_rating: str | None = Field(default=None, max_length=32)
    genres: list[str] = Field(default_factory=list)
    status: str = MovieStatuses.PLANNED

    @model_validator(mode="before")
    @classmethod
    def populate_legacy_status(cls, value: Any) -> Any:
        """Accept legacy payloads/documents that still send `is_active`."""
        return _populate_legacy_movie_status(value)

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

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Restrict movie status values to the supported lifecycle states."""
        if value not in MOVIE_STATUS_VALUES:
            raise ValueError("Unsupported movie status.")
        return value


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
    status: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_legacy_status(cls, value: Any) -> Any:
        """Accept legacy partial updates that still send `is_active`."""
        return _populate_legacy_movie_status(value)

    @field_validator("genres")
    @classmethod
    def normalize_genres(cls, value: list[str] | None) -> list[str] | None:
        """Trim, deduplicate, and drop blank genre values for partial updates too."""
        if value is None:
            return None
        return MovieBase.normalize_genres(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        """Validate partial status updates when status is provided."""
        if value is None:
            return None
        return MovieBase.validate_status(value)


class MovieRead(MovieBase):
    """Movie DTO returned by the API."""

    id: str
    created_at: datetime
    updated_at: datetime | None = None
