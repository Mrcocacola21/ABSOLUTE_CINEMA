"""Shared movie genre registry and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GenreDefinition:
    """One supported canonical genre."""

    code: str
    uk: str
    en: str
    aliases: tuple[str, ...] = ()


GENRE_DEFINITIONS: tuple[GenreDefinition, ...] = (
    GenreDefinition("action", uk="Бойовик", en="Action"),
    GenreDefinition("adventure", uk="Пригоди", en="Adventure"),
    GenreDefinition("animation", uk="Анімація", en="Animation", aliases=("animated", "cartoon")),
    GenreDefinition(
        "biographical",
        uk="Біографічний",
        en="Biographical",
        aliases=("biopic", "biography"),
    ),
    GenreDefinition("comedy", uk="Комедія", en="Comedy"),
    GenreDefinition("crime", uk="Кримінальний", en="Crime"),
    GenreDefinition("detective", uk="Детектив", en="Detective"),
    GenreDefinition("documentary", uk="Документальний", en="Documentary", aliases=("docu", "doc")),
    GenreDefinition("drama", uk="Драма", en="Drama"),
    GenreDefinition("family", uk="Сімейний", en="Family"),
    GenreDefinition("fantasy", uk="Фентезі", en="Fantasy"),
    GenreDefinition("historical", uk="Історичний", en="Historical", aliases=("history",)),
    GenreDefinition("horror", uk="Жахи", en="Horror"),
    GenreDefinition("melodrama", uk="Мелодрама", en="Melodrama"),
    GenreDefinition("musical", uk="Мюзикл", en="Musical"),
    GenreDefinition("mystery", uk="Містика", en="Mystery"),
    GenreDefinition("romance", uk="Романтика", en="Romance", aliases=("romantic",)),
    GenreDefinition(
        "science_fiction",
        uk="Фантастика",
        en="Science Fiction",
        aliases=("sci-fi", "sci fi", "scifi", "fantastic", "фантастика"),
    ),
    GenreDefinition("sport", uk="Спортивний", en="Sport", aliases=("sports",)),
    GenreDefinition("thriller", uk="Трилер", en="Thriller"),
    GenreDefinition("war", uk="Воєнний", en="War"),
    GenreDefinition("western", uk="Вестерн", en="Western"),
)

SUPPORTED_GENRE_CODES: tuple[str, ...] = tuple(definition.code for definition in GENRE_DEFINITIONS)
GENRE_LABELS_BY_CODE: dict[str, dict[str, str]] = {
    definition.code: {"uk": definition.uk, "en": definition.en}
    for definition in GENRE_DEFINITIONS
}

_NON_ALNUM_PATTERN = re.compile(r"[^\w]+", flags=re.UNICODE)


def _normalize_lookup_key(value: str) -> str:
    cleaned = _NON_ALNUM_PATTERN.sub("_", value.casefold()).strip("_")
    return re.sub(r"_+", "_", cleaned)


GENRE_CODE_BY_LOOKUP_KEY: dict[str, str] = {}
for definition in GENRE_DEFINITIONS:
    for candidate in (definition.code, definition.uk, definition.en, *definition.aliases):
        GENRE_CODE_BY_LOOKUP_KEY[_normalize_lookup_key(candidate)] = definition.code


def normalize_genre_code(value: str) -> str:
    """Return a canonical genre code for the provided code, label, or alias."""
    lookup_key = _normalize_lookup_key(value)
    if not lookup_key:
        raise ValueError("Genre value cannot be blank.")

    normalized = GENRE_CODE_BY_LOOKUP_KEY.get(lookup_key)
    if normalized is None:
        raise ValueError(f"Unsupported genre code: {value}.")
    return normalized


def normalize_genre_codes(values: list[str]) -> list[str]:
    """Normalize, validate, and deduplicate a genre list."""
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_value in values:
        cleaned = raw_value.strip()
        if not cleaned:
            continue

        normalized_code = normalize_genre_code(cleaned)
        if normalized_code in seen:
            continue

        seen.add(normalized_code)
        normalized.append(normalized_code)

    return normalized
