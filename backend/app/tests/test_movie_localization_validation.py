"""Focused tests for language-aware localized movie validation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.constants import MovieStatuses
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate


def build_valid_movie_payload() -> dict[str, object]:
    return {
        "title": {
            "uk": "Євангеліон 3.0+1.0: Востаннє",
            "en": "Evangelion 3.0+1.0: Thrice Upon a Time",
        },
        "description": {
            "uk": "Аніме в IMAX 3D про фінальну битву та останній вибір.",
            "en": "An IMAX 3D anime feature about the final battle and the last choice.",
        },
        "duration_minutes": 155,
        "genres": ["animation", "science_fiction"],
        "status": MovieStatuses.PLANNED,
    }


def extract_validation_messages(error: ValidationError) -> list[str]:
    return [str(entry["msg"]) for entry in error.errors()]


def test_movie_create_accepts_language_matched_localized_fields() -> None:
    payload = MovieCreate(**build_valid_movie_payload())

    assert payload.title.uk == "Євангеліон 3.0+1.0: Востаннє"
    assert payload.title.en == "Evangelion 3.0+1.0: Thrice Upon a Time"
    assert payload.description.uk.startswith("Аніме в IMAX 3D")
    assert payload.description.en.startswith("An IMAX 3D anime feature")


@pytest.mark.parametrize(
    ("field_updates", "expected_message"),
    [
        (
            {
                "title": {
                    "uk": "Attack on Titan",
                    "en": "Attack on Titan",
                }
            },
            "title.uk must contain Ukrainian text.",
        ),
        (
            {
                "title": {
                    "uk": "Атака титанів",
                    "en": "Атака титанів",
                }
            },
            "title.en must contain English text.",
        ),
        (
            {
                "description": {
                    "uk": "A haunted train crosses the city at midnight.",
                    "en": "A haunted train crosses the city at midnight.",
                }
            },
            "description.uk must contain Ukrainian text.",
        ),
        (
            {
                "description": {
                    "uk": "Опівночі містом мчить примарний потяг.",
                    "en": "Опівночі містом мчить примарний потяг.",
                }
            },
            "description.en must contain English text.",
        ),
    ],
)
def test_movie_create_rejects_wrong_language_in_localized_fields(
    field_updates: dict[str, dict[str, str]],
    expected_message: str,
) -> None:
    payload = {
        **build_valid_movie_payload(),
        **field_updates,
    }

    with pytest.raises(ValidationError) as error:
        MovieCreate(**payload)

    assert any(expected_message in message for message in extract_validation_messages(error.value))


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {"title": {"uk": "Chainsaw Man"}},
            "title.uk must contain Ukrainian text.",
        ),
        (
            {"description": {"en": "Український опис"}},
            "description.en must contain English text.",
        ),
    ],
)
def test_movie_update_rejects_invalid_language_in_partial_localized_updates(
    payload: dict[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        MovieUpdate(**payload)

    assert any(expected_message in message for message in extract_validation_messages(error.value))


def test_movie_read_accepts_legacy_localized_text_already_stored_in_database() -> None:
    now = datetime.now(tz=timezone.utc)

    movie = MovieRead(
        id="legacy-movie-1",
        title={"uk": "TEST", "en": "TEST"},
        description={"uk": "TEST", "en": "TEST"},
        duration_minutes=95,
        poster_url=None,
        age_rating="PG-13",
        genres=["drama"],
        status=MovieStatuses.PLANNED,
        created_at=now,
        updated_at=None,
    )

    assert movie.title.uk == "TEST"
    assert movie.description.en == "TEST"
