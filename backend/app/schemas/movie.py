"""Movie-related schemas."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.core.constants import MOVIE_STATUS_VALUES, MovieStatuses
from app.core.genres import normalize_genre_codes
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText, LocalizedTextUpdate, merge_localized_text


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

    title: LocalizedText
    description: LocalizedText
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
        """Normalize genres into supported canonical codes."""
        return normalize_genre_codes(value)

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

    title: LocalizedTextUpdate | None = None
    description: LocalizedTextUpdate | None = None
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
        """Normalize genre codes for partial updates too."""
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


def merge_movie_localized_updates(
    movie: MovieRead,
    updates: dict[str, object],
) -> dict[str, object]:
    """Merge partial localized update payloads into the current movie value."""
    merged = dict(updates)

    if "title" in merged and merged["title"] is not None:
        merged["title"] = merge_localized_text(
            movie.title,
            LocalizedTextUpdate.model_validate(merged["title"]),
        ).model_dump(mode="python")

    if "description" in merged and merged["description"] is not None:
        merged["description"] = merge_localized_text(
            movie.description,
            LocalizedTextUpdate.model_validate(merged["description"]),
        ).model_dump(mode="python")

    return merged


def build_canonical_movie_fields(movie: MovieRead) -> dict[str, object]:
    """Return canonical movie fields for MongoDB storage."""
    return {
        "title": movie.title.model_dump(mode="python"),
        "description": movie.description.model_dump(mode="python"),
        "genres": list(movie.genres),
    }


def build_movie_normalization_updates(
    document: Mapping[str, object],
    movie: MovieRead,
) -> dict[str, object]:
    """Return updates required to rewrite legacy movie documents into the canonical shape."""
    canonical_fields = build_canonical_movie_fields(movie)
    return {
        field_name: canonical_value
        for field_name, canonical_value in canonical_fields.items()
        if document.get(field_name) != canonical_value
    }
