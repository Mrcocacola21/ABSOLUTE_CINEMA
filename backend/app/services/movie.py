"""Movie service for public movie browsing."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.constants import MovieStatuses
from app.core.exceptions import NotFoundException
from app.repositories.movies import MovieRepository
from app.repositories.sessions import SessionRepository
from app.schemas.movie import MovieRead
from app.services.movie_status import MovieStatusManager


class MovieService:
    """Service exposing public read operations for movies."""

    def __init__(
        self,
        movie_repository: MovieRepository,
        session_repository: SessionRepository,
    ) -> None:
        self.movie_repository = movie_repository
        self.movie_status_manager = MovieStatusManager(
            movie_repository=movie_repository,
            session_repository=session_repository,
        )

    async def list_movies(self, *, include_inactive: bool = False) -> list[MovieRead]:
        """Return public movie catalog entries ordered by title."""
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        movies = await self.movie_repository.list_movies(active_only=not include_inactive)
        return [MovieRead.model_validate(movie) for movie in movies]

    async def get_movie(self, movie_id: str, *, include_inactive: bool = False) -> MovieRead:
        """Return a movie for public views."""
        now = datetime.now(tz=timezone.utc)
        await self.movie_status_manager.refresh_statuses(current_time=now)
        movie = await self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise NotFoundException("Movie was not found.")
        parsed_movie = MovieRead.model_validate(movie)
        if not include_inactive and parsed_movie.status != MovieStatuses.ACTIVE:
            raise NotFoundException("Movie was not found.")
        return parsed_movie
