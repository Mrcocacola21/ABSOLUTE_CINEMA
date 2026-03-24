"""Public movie browsing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.services import get_movie_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.movie import MovieRead
from app.services.movie import MovieService

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("", response_model=ApiResponse[list[MovieRead]])
async def list_movies(
    include_inactive: bool = Query(default=False),
    movie_service: MovieService = Depends(get_movie_service),
) -> ApiResponse[list[MovieRead]]:
    """Return movies for public browsing."""
    movies = await movie_service.list_movies(include_inactive=include_inactive)
    return ApiResponseFactory.success(data=movies, message="Movies loaded.")


@router.get("/{movie_id}", response_model=ApiResponse[MovieRead])
async def get_movie(
    movie_id: str,
    include_inactive: bool = Query(default=False),
    movie_service: MovieService = Depends(get_movie_service),
) -> ApiResponse[MovieRead]:
    """Return a single movie for public browsing."""
    movie = await movie_service.get_movie(movie_id, include_inactive=include_inactive)
    return ApiResponseFactory.success(data=movie, message="Movie loaded.")
