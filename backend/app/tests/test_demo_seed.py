"""Unit tests for deterministic demo seed data generation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from app.core.constants import MovieStatuses, SessionStatuses
from app.seeds.demo_dataset import (
    DEMO_ADMIN_EMAIL,
    DEMO_SHARED_PASSWORD,
    build_demo_seed_data,
    demo_credentials,
)
from app.seeds.demo_seed import DemoSeedSummary, _log_summary


def test_build_demo_seed_data_returns_valid_presentation_ready_dataset() -> None:
    reference_now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)

    dataset = build_demo_seed_data(reference_now=reference_now)

    assert dataset.collection_counts == {
        "users": 5,
        "movies": 10,
        "sessions": 20,
        "orders": 9,
        "tickets": 20,
    }
    assert {movie["status"] for movie in dataset.movies} == {
        MovieStatuses.ACTIVE,
        MovieStatuses.PLANNED,
        MovieStatuses.DEACTIVATED,
    }
    assert {session["status"] for session in dataset.sessions} == {
        SessionStatuses.SCHEDULED,
        SessionStatuses.COMPLETED,
        SessionStatuses.CANCELLED,
    }
    assert all(str(movie["poster_url"]).startswith("/demo-posters/") for movie in dataset.movies)


def test_demo_credentials_include_seeded_admin_account() -> None:
    credentials = demo_credentials()

    assert credentials[0]["email"] == DEMO_ADMIN_EMAIL
    assert credentials[0]["password"] == DEMO_SHARED_PASSWORD
    assert credentials[0]["role"] == "admin"
    assert all(credential["password"] == DEMO_SHARED_PASSWORD for credential in credentials)


def test_demo_seed_summary_logging_uses_logger_without_exposing_passwords(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cinema_showcase")

    _log_summary(
        DemoSeedSummary(
            database_name="cinema_showcase",
            reset_applied=True,
            seed_version="demo-seed-v1",
            counts={
                "users": 5,
                "movies": 10,
                "sessions": 20,
                "orders": 9,
                "tickets": 20,
            },
            movie_status_counts={"active": 4},
            session_status_counts={"scheduled": 8},
        )
    )

    assert DEMO_SHARED_PASSWORD not in caplog.text
    assert DEMO_ADMIN_EMAIL in caplog.text
    assert "password is intentionally not logged" in caplog.text
