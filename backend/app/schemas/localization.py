"""Reusable localized text schemas and helpers."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from app.schemas.common import BaseSchema

SUPPORTED_LANGUAGE_CODES = ("uk", "en")


def normalize_language_code(value: str | None) -> str:
    """Map language variants to the supported language set."""
    if value and value.lower().startswith("en"):
        return "en"
    return "uk"


def _coerce_localized_text_payload(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip()
        return {"uk": cleaned, "en": cleaned}

    if not isinstance(value, dict):
        return value

    uk = str(value.get("uk", "")).strip() if value.get("uk") is not None else ""
    en = str(value.get("en", "")).strip() if value.get("en") is not None else ""

    if uk and not en:
        en = uk
    if en and not uk:
        uk = en

    return {"uk": uk, "en": en}


class LocalizedText(BaseSchema):
    """Localized text stored in both supported UI languages."""

    uk: str = Field(min_length=1)
    en: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, value: Any) -> Any:
        """Accept legacy flat strings and normalize partial localized dictionaries."""
        return _coerce_localized_text_payload(value)

    def resolve(self, language: str) -> str:
        """Return the preferred translation with Ukrainian fallback."""
        preferred_language = normalize_language_code(language)
        preferred_value = getattr(self, preferred_language, "").strip()
        if preferred_value:
            return preferred_value
        return self.uk.strip() or self.en.strip()


class LocalizedTextUpdate(BaseSchema):
    """Partial localized text update payload."""

    uk: str | None = Field(default=None, min_length=1)
    en: str | None = Field(default=None, min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, value: Any) -> Any:
        """Accept legacy flat strings for partial updates too."""
        if isinstance(value, str):
            cleaned = value.strip()
            return {"uk": cleaned, "en": cleaned}

        if not isinstance(value, dict):
            return value

        normalized: dict[str, str] = {}
        if value.get("uk") is not None:
            normalized["uk"] = str(value["uk"]).strip()
        if value.get("en") is not None:
            normalized["en"] = str(value["en"]).strip()
        return normalized

    @model_validator(mode="after")
    def ensure_any_value_present(self) -> "LocalizedTextUpdate":
        """Reject empty update objects when the field is explicitly provided."""
        if self.uk is None and self.en is None:
            raise ValueError("At least one localized value must be provided.")
        return self


def merge_localized_text(current: LocalizedText, updates: LocalizedTextUpdate | LocalizedText) -> LocalizedText:
    """Merge a partial localized update into an existing localized text value."""
    if isinstance(updates, LocalizedText):
        return updates

    return LocalizedText(
        uk=updates.uk if updates.uk is not None else current.uk,
        en=updates.en if updates.en is not None else current.en,
    )
