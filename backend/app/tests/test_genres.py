"""Unit tests for movie genre normalization helpers."""

from __future__ import annotations

import pytest

from app.core.genres import (
    GENRE_LABELS_BY_CODE,
    SUPPORTED_GENRE_CODES,
    normalize_genre_code,
    normalize_genre_codes,
)


@pytest.mark.parametrize(
    ("raw_value", "expected_code"),
    [
        ("science_fiction", "science_fiction"),
        ("Science Fiction", "science_fiction"),
        ("SCI-FI", "science_fiction"),
        ("sci fi", "science_fiction"),
        ("animated", "animation"),
        ("cartoon", "animation"),
        ("biopic", "biographical"),
        ("sports", "sport"),
        ("romantic", "romance"),
        ("doc", "documentary"),
    ],
)
def test_normalize_genre_code_accepts_codes_labels_and_aliases(raw_value: str, expected_code: str) -> None:
    assert normalize_genre_code(raw_value) == expected_code


def test_normalize_genre_code_handles_punctuation_like_canonical_underscores() -> None:
    assert normalize_genre_code("science-fiction") == "science_fiction"
    assert normalize_genre_code(" science   fiction ") == "science_fiction"


def test_normalize_genre_code_rejects_blank_values() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        normalize_genre_code("   ")


def test_normalize_genre_code_rejects_unknown_values_with_original_input() -> None:
    with pytest.raises(ValueError, match="Unsupported genre code: cooking show."):
        normalize_genre_code("cooking show")


def test_normalize_genre_codes_deduplicates_after_alias_resolution_and_preserves_order() -> None:
    normalized = normalize_genre_codes(
        [
            "Drama",
            "sci-fi",
            "science fiction",
            "",
            " animated ",
            "cartoon",
            "Drama",
        ]
    )

    assert normalized == ["drama", "science_fiction", "animation"]


def test_supported_genre_registry_exposes_labels_for_every_canonical_code() -> None:
    assert "science_fiction" in SUPPORTED_GENRE_CODES
    assert set(GENRE_LABELS_BY_CODE) == set(SUPPORTED_GENRE_CODES)
    assert GENRE_LABELS_BY_CODE["science_fiction"]["en"] == "Science Fiction"
