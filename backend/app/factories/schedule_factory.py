"""Factories for schedule-oriented DTOs."""

from __future__ import annotations

from app.schemas.movie import MovieRead
from app.schemas.session import ScheduleItemRead, SessionDetailsRead, SessionRead


class ScheduleItemFactory:
    """Create schedule DTOs optimized for frontend display."""

    @staticmethod
    def build(session: SessionRead, movie: MovieRead) -> ScheduleItemRead:
        """Create a schedule item using the related movie data."""
        return ScheduleItemRead(
            id=session.id,
            movie_id=session.movie_id,
            movie_title=movie.title,
            poster_url=str(movie.poster_url) if movie.poster_url else None,
            age_rating=movie.age_rating,
            genres=movie.genres,
            start_time=session.start_time,
            end_time=session.end_time,
            price=session.price,
            status=session.status,
            available_seats=session.available_seats,
            total_seats=session.total_seats,
        )


class SessionDetailsFactory:
    """Create session details DTOs enriched with movie information."""

    @staticmethod
    def build(session: SessionRead, movie: MovieRead) -> SessionDetailsRead:
        """Combine session and movie information for the details screen."""
        return SessionDetailsRead(**session.model_dump(), movie=movie)
