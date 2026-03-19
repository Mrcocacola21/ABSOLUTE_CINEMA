"""Unit tests for session schema invariants."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.session import SessionRead


def test_session_read_rejects_available_seats_above_total_seats() -> None:
    now = datetime.now(tz=timezone.utc)

    with pytest.raises(ValidationError):
        SessionRead(
            id="session-1",
            movie_id="movie-1",
            start_time=now,
            end_time=now + timedelta(minutes=90),
            price=200,
            status="scheduled",
            total_seats=96,
            available_seats=97,
            created_at=now,
            updated_at=None,
        )
