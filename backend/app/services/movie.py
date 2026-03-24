"""Movie service for public movie browsing."""

from __future__ import annotations

from app.core.exceptions import NotFoundException
from app.repositories.movies import MovieRepository
from app.schemas.movie import MovieRead


class MovieService:
    """Service exposing public read operations for movies."""

    def __init__(self, movie_repository: MovieRepository) -> None:
        self.movie_repository = movie_repository

    async def list_movies(self, *, include_inactive: bool = False) -> list[MovieRead]:
        """Return public movie catalog entries ordered by title."""
        movies = await self.movie_repository.list_movies(active_only=not include_inactive)
        return [MovieRead.model_validate(movie) for movie in movies]

    async def get_movie(self, movie_id: str, *, include_inactive: bool = False) -> MovieRead:
        """Return a movie for public views."""
        movie = await self.movie_repository.get_by_id(movie_id)
        if movie is None:
            raise NotFoundException("Movie was not found.")
        if not include_inactive and not movie.get("is_active", True):
            raise NotFoundException("Movie was not found.")
        return MovieRead.model_validate(movie)
