"""Public movie browsing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.services import get_movie_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.movie import MovieRead
from app.services.movie import MovieService

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("", response_model=ApiResponse[list[MovieRead]])
async def list_movies(
    movie_service: MovieService = Depends(get_movie_service),
) -> ApiResponse[list[MovieRead]]:
    """Return active movies that can appear in the public schedule."""
    movies = await movie_service.list_available_movies()
    return ApiResponseFactory.success(data=movies, message="Movies loaded.")
