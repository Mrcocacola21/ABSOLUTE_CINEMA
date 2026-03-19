"""Movie service for public movie browsing."""

from __future__ import annotations

from app.repositories.movies import MovieRepository
from app.schemas.movie import MovieRead


class MovieService:
    """Service exposing public read operations for movies."""

    def __init__(self, movie_repository: MovieRepository) -> None:
        self.movie_repository = movie_repository

    async def list_available_movies(self) -> list[MovieRead]:
        """Return active movies ordered by title."""
        movies = await self.movie_repository.list_movies(active_only=True)
        return [MovieRead.model_validate(movie) for movie in movies]
