"""Helpers for keeping movie lifecycle status aligned with session activity."""

from __future__ import annotations

from datetime import datetime

from app.core.constants import MovieStatuses
from app.repositories.movies import MovieRepository
from app.repositories.sessions import SessionRepository
from app.schemas.movie import MovieRead


class MovieStatusManager:
    """Synchronize explicit movie status values with future scheduled sessions."""

    def __init__(
        self,
        movie_repository: MovieRepository,
        session_repository: SessionRepository,
    ) -> None:
        self.movie_repository = movie_repository
        self.session_repository = session_repository

    async def refresh_statuses(self, *, current_time: datetime) -> None:
        """Promote scheduled movies to active and demote stale active movies."""
        await self.session_repository.sync_completed_sessions(current_time=current_time, updated_at=current_time)

        movies = await self.movie_repository.list_movies(active_only=False)
        if not movies:
            return

        future_movie_ids = set(
            await self.session_repository.list_movie_ids_with_future_scheduled_sessions(current_time=current_time)
        )

        for movie_document in movies:
            movie = MovieRead.model_validate(movie_document)
            next_status = self._resolve_next_status(movie=movie, future_movie_ids=future_movie_ids)
            if next_status == movie.status:
                continue
            await self.movie_repository.update_movie(
                movie_id=movie.id,
                updates={"status": next_status},
                updated_at=current_time,
            )

    async def has_future_sessions(self, movie_id: str, *, current_time: datetime) -> bool:
        """Return whether a movie currently qualifies as active because of future sessions."""
        return await self.session_repository.has_future_scheduled_sessions(movie_id, current_time=current_time)

    def _resolve_next_status(self, *, movie: MovieRead, future_movie_ids: set[str]) -> str:
        if movie.id in future_movie_ids:
            return MovieStatuses.ACTIVE
        if movie.status == MovieStatuses.ACTIVE:
            return MovieStatuses.DEACTIVATED
        return movie.status
