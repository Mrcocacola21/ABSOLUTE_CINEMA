"""Reusable localized text schemas and helpers."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import BaseSchema

SUPPORTED_LANGUAGE_CODES = ("uk", "en")
LATIN_TOKEN_PATTERN = re.compile(r"[A-Za-z]+")
CYRILLIC_LETTER_PATTERN = re.compile(r"[\u0400-\u04FF]")


def _is_allowed_ukrainian_inline_latin_token(token: str) -> bool:
    """Allow a narrow set of Latin fragments inside Ukrainian text.

    Ukrainian movie copy sometimes includes short technical labels such as
    `IMAX`, `OVA`, `TV`, or `x`. Longer Latin words still indicate that the
    field was likely filled in with English text instead of Ukrainian.
    """

    return token.casefold() == "x" or (token.isupper() and len(token) <= 5)


def validate_expected_text_language(
    value: str,
    *,
    expected_language: str,
    field_name: str,
) -> str:
    """Reject clearly wrong-language localized movie text without blocking title formatting.

    The rule is intentionally heuristic rather than full language detection:
    we look for Latin vs Cyrillic letters, allow punctuation/numbers, and keep a
    small exception list for uppercase technical labels in Ukrainian copy.
    """

    latin_tokens = LATIN_TOKEN_PATTERN.findall(value)
    latin_letters = sum(len(token) for token in latin_tokens)
    cyrillic_letters = len(CYRILLIC_LETTER_PATTERN.findall(value))

    if expected_language == "uk":
        if latin_letters > 0 and cyrillic_letters == 0:
            raise ValueError(f"{field_name} must contain Ukrainian text.")
        if cyrillic_letters == 0:
            return value

        invalid_latin_tokens = [
            token for token in latin_tokens if not _is_allowed_ukrainian_inline_latin_token(token)
        ]
        if invalid_latin_tokens:
            raise ValueError(f"{field_name} must contain Ukrainian text.")
        return value

    if expected_language == "en":
        if cyrillic_letters > 0:
            raise ValueError(f"{field_name} must contain English text.")
        return value

    raise ValueError(f"Unsupported language code: {expected_language}")


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

    normalized = {
        key: raw_value
        for key, raw_value in value.items()
        if key not in SUPPORTED_LANGUAGE_CODES
    }

    uk = str(value.get("uk", "")).strip() if value.get("uk") is not None else ""
    en = str(value.get("en", "")).strip() if value.get("en") is not None else ""

    if uk and not en:
        en = uk
    if en and not uk:
        uk = en

    return {
        **normalized,
        "uk": uk,
        "en": en,
    }


class LocalizedText(BaseSchema):
    """Localized text stored in both supported UI languages."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    uk: str = Field(
        min_length=1,
        description="Ukrainian localized value.",
        examples=["Інтерстеллар"],
    )
    en: str = Field(
        min_length=1,
        description="English localized value.",
        examples=["Interstellar"],
    )

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

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    uk: str | None = Field(
        default=None,
        min_length=1,
        description="Updated Ukrainian localized value.",
        examples=["Оновлений український опис"],
    )
    en: str | None = Field(
        default=None,
        min_length=1,
        description="Updated English localized value.",
        examples=["Updated English description"],
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, value: Any) -> Any:
        """Accept legacy flat strings for partial updates too."""
        if isinstance(value, str):
            cleaned = value.strip()
            return {"uk": cleaned, "en": cleaned}

        if not isinstance(value, dict):
            return value

        normalized: dict[str, Any] = {
            key: raw_value
            for key, raw_value in value.items()
            if key not in SUPPORTED_LANGUAGE_CODES
        }
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
