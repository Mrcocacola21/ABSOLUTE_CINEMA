"""Movie-related schemas."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Any, cast

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError, field_validator, model_validator
from pydantic.networks import HttpUrl

from app.core.constants import MOVIE_STATUS_VALUES, MovieStatuses
from app.core.genres import normalize_genre_code
from app.schemas.common import BaseSchema
from app.schemas.localization import (
    LocalizedText,
    LocalizedTextUpdate,
    merge_localized_text,
    validate_expected_text_language,
)

MOVIE_DURATION_MINUTES_MIN = 40
MOVIE_DURATION_MINUTES_MAX = 360
MOVIE_TITLE_MAX_LENGTH = 150
MOVIE_DESCRIPTION_MAX_LENGTH = 2000
MOVIE_AGE_RATING_MAX_LENGTH = 16

POSTER_URL_ADAPTER = TypeAdapter(HttpUrl)
POSTER_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".svg")
POSTER_ASSET_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9/_\.-]*$")
AGE_RATING_PATTERN = re.compile(r"^[A-Za-z0-9+ -]+$")


def _validate_localized_text_length(
    value: LocalizedText | LocalizedTextUpdate | None,
    *,
    field_name: str,
    max_length: int,
) -> LocalizedText | LocalizedTextUpdate | None:
    if value is None:
        return None

    for language_code in ("uk", "en"):
        localized_value = getattr(value, language_code, None)
        if localized_value is None:
            continue
        if len(localized_value) > max_length:
            raise ValueError(
                f"{field_name}.{language_code} must be at most {max_length} characters long."
            )
    return value


def _validate_localized_text_language(
    value: LocalizedText | LocalizedTextUpdate | None,
    *,
    field_name: str,
) -> LocalizedText | LocalizedTextUpdate | None:
    if value is None:
        return None

    for language_code in ("uk", "en"):
        localized_value = getattr(value, language_code, None)
        if localized_value is None:
            continue
        validate_expected_text_language(
            localized_value,
            expected_language=language_code,
            field_name=f"{field_name}.{language_code}",
        )
    return value


def _normalize_and_validate_poster_url(value: object) -> str | None:
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if candidate.startswith("/"):
        if not POSTER_ASSET_PATH_PATTERN.fullmatch(candidate):
            raise ValueError(
                "poster_url must be an absolute http(s) URL or a root-relative image asset path."
            )
        if not candidate.lower().endswith(POSTER_IMAGE_SUFFIXES):
            raise ValueError(
                "poster_url asset paths must end with .jpg, .jpeg, .png, .webp, or .svg."
            )
        return candidate

    try:
        return str(POSTER_URL_ADAPTER.validate_python(candidate))
    except ValidationError as exc:
        raise ValueError(
            "poster_url must be an absolute http(s) URL or a root-relative image asset path."
        ) from exc


def _normalize_age_rating(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = " ".join(value.split())
    if not normalized:
        return None
    if len(normalized) > MOVIE_AGE_RATING_MAX_LENGTH:
        raise ValueError(
            f"age_rating must be at most {MOVIE_AGE_RATING_MAX_LENGTH} characters long."
        )
    if not AGE_RATING_PATTERN.fullmatch(normalized):
        raise ValueError("age_rating may only contain letters, numbers, spaces, '+' and '-'.")
    return normalized


def _normalize_movie_genres(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in value:
        cleaned = raw_value.strip()
        if not cleaned:
            continue

        normalized_code = normalize_genre_code(cleaned)
        if normalized_code in seen:
            raise ValueError("Duplicate genre codes are not allowed.")

        seen.add(normalized_code)
        normalized.append(normalized_code)

    return normalized


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


def _validate_movie_title(
    value: LocalizedText | LocalizedTextUpdate | None,
) -> LocalizedText | LocalizedTextUpdate | None:
    return _validate_localized_text_language(
        _validate_localized_text_length(
            value,
            field_name="title",
            max_length=MOVIE_TITLE_MAX_LENGTH,
        ),
        field_name="title",
    )


def _validate_movie_description(
    value: LocalizedText | LocalizedTextUpdate | None,
) -> LocalizedText | LocalizedTextUpdate | None:
    return _validate_localized_text_language(
        _validate_localized_text_length(
            value,
            field_name="description",
            max_length=MOVIE_DESCRIPTION_MAX_LENGTH,
        ),
        field_name="description",
    )


class MovieBase(BaseSchema):
    """Shared movie fields."""

    title: LocalizedText = Field(
        description="Localized movie title used across the public catalog, schedule, and admin views.",
    )
    description: LocalizedText = Field(
        description="Localized movie description shown on movie details screens and admin forms.",
    )
    duration_minutes: int = Field(
        ge=MOVIE_DURATION_MINUTES_MIN,
        le=MOVIE_DURATION_MINUTES_MAX,
        description="Movie runtime in minutes.",
    )
    poster_url: str | None = Field(
        default=None,
        description="External HTTP(S) poster URL or root-relative demo asset path.",
    )
    age_rating: str | None = Field(
        default=None,
        max_length=MOVIE_AGE_RATING_MAX_LENGTH,
        description="Optional age-rating label such as `PG-13`, `16+`, or `R`.",
    )
    genres: list[str] = Field(
        default_factory=list,
        description="Normalized genre codes used by the frontend for badges and filtering.",
        examples=[["science_fiction", "drama"]],
    )
    status: str = Field(
        default=MovieStatuses.PLANNED,
        description="Movie lifecycle status managed by the backend.",
        json_schema_extra={"enum": list(MOVIE_STATUS_VALUES)},
    )

    @model_validator(mode="before")
    @classmethod
    def populate_legacy_status(cls, value: Any) -> Any:
        """Accept legacy payloads/documents that still send `is_active`."""
        return _populate_legacy_movie_status(value)

    @field_validator("poster_url", mode="before")
    @classmethod
    def normalize_poster_url(cls, value: object) -> str | None:
        """Accept either external poster URLs or local demo asset paths."""
        return _normalize_and_validate_poster_url(value)

    @field_validator("age_rating")
    @classmethod
    def validate_age_rating(cls, value: str | None) -> str | None:
        """Normalize optional age ratings and reject blank or noisy values."""
        return _normalize_age_rating(value)

    @field_validator("genres")
    @classmethod
    def normalize_genres(cls, value: list[str]) -> list[str]:
        """Normalize genres into supported canonical codes."""
        return _normalize_movie_genres(value) or []

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Restrict movie status values to the supported lifecycle states."""
        if value not in MOVIE_STATUS_VALUES:
            raise ValueError("Unsupported movie status.")
        return value


class MovieCreate(MovieBase):
    """Payload for creating a movie."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: LocalizedText) -> LocalizedText:
        """Require language-matched localized titles for newly created movies."""
        return cast(LocalizedText, _validate_movie_title(value))

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: LocalizedText) -> LocalizedText:
        """Require language-matched localized descriptions for newly created movies."""
        return cast(LocalizedText, _validate_movie_description(value))


class MovieUpdate(BaseSchema):
    """Payload for updating a movie."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    title: LocalizedTextUpdate | None = Field(
        default=None,
        description="Partial localized title update.",
    )
    description: LocalizedTextUpdate | None = Field(
        default=None,
        description="Partial localized description update.",
    )
    duration_minutes: int | None = Field(
        default=None,
        ge=MOVIE_DURATION_MINUTES_MIN,
        le=MOVIE_DURATION_MINUTES_MAX,
        description="Updated movie runtime in minutes.",
    )
    poster_url: str | None = Field(
        default=None,
        description="Updated poster URL or root-relative asset path.",
    )
    age_rating: str | None = Field(
        default=None,
        max_length=MOVIE_AGE_RATING_MAX_LENGTH,
        description="Updated age-rating label.",
    )
    genres: list[str] | None = Field(
        default=None,
        description="Updated list of normalized genre codes.",
        examples=[["drama", "mystery"]],
    )
    status: str | None = Field(
        default=None,
        description="Updated movie lifecycle status.",
        json_schema_extra={"enum": list(MOVIE_STATUS_VALUES)},
    )

    @model_validator(mode="before")
    @classmethod
    def populate_legacy_status(cls, value: Any) -> Any:
        """Accept legacy partial updates that still send `is_active`."""
        return _populate_legacy_movie_status(value)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: LocalizedTextUpdate | None) -> LocalizedTextUpdate | None:
        """Apply the same title length rules to partial updates."""
        return cast(LocalizedTextUpdate | None, _validate_movie_title(value))

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: LocalizedTextUpdate | None) -> LocalizedTextUpdate | None:
        """Apply the same description limits to partial updates."""
        return cast(LocalizedTextUpdate | None, _validate_movie_description(value))

    @field_validator("poster_url", mode="before")
    @classmethod
    def normalize_poster_url(cls, value: object) -> str | None:
        """Normalize explicit poster updates, including empty strings from forms."""
        return _normalize_and_validate_poster_url(value)

    @field_validator("age_rating")
    @classmethod
    def validate_age_rating(cls, value: str | None) -> str | None:
        """Normalize optional age-rating updates."""
        return _normalize_age_rating(value)

    @field_validator("genres")
    @classmethod
    def normalize_genres(cls, value: list[str] | None) -> list[str] | None:
        """Normalize genre codes for partial updates too."""
        return _normalize_movie_genres(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        """Validate partial status updates when status is provided."""
        if value is None:
            return None
        return MovieBase.validate_status(value)


class MovieRead(MovieBase):
    """Movie DTO returned by the API.

    Read models stay tolerant of legacy localized text already stored in MongoDB,
    while create/update payloads continue to enforce the stricter language rules.
    """

    id: str = Field(description="Movie identifier.")
    created_at: datetime = Field(description="Movie creation timestamp in ISO 8601 format.")
    updated_at: datetime | None = Field(default=None, description="Last movie update timestamp, if any.")


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
