"""Public movie browsing endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.docs import NOT_FOUND_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE, merge_openapi_responses
from app.api.dependencies.services import get_movie_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.movie import MovieRead
from app.services.movie import MovieService

router = APIRouter(prefix="/movies", tags=["movies"])

IncludeInactiveQuery = Annotated[
    bool,
    Query(
        description=(
            "Set to `true` to include planned and deactivated movies in the catalog. "
            "By default, the public catalog returns only active movies."
        ),
    ),
]

@router.get(
    "",
    response_model=ApiResponse[list[MovieRead]],
    summary="Browse movies",
    description=(
        "Return the public movie catalog. The `include_inactive` flag is useful for demos and admin-adjacent "
        "exploration because it exposes planned and archived movies as well."
    ),
    response_description="Wrapped list of movies for catalog browsing.",
    responses=VALIDATION_ERROR_RESPONSE,
)
async def list_movies(
    include_inactive: IncludeInactiveQuery = False,
    movie_service: MovieService = Depends(get_movie_service),
) -> ApiResponse[list[MovieRead]]:
    """Return movies for public browsing."""
    movies = await movie_service.list_movies(include_inactive=include_inactive)
    return ApiResponseFactory.success(data=movies, message="Movies loaded.")


@router.get(
    "/{movie_id}",
    response_model=ApiResponse[MovieRead],
    summary="Get movie details",
    description="Return one movie from the public catalog by its identifier.",
    response_description="Wrapped movie details.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def get_movie(
    movie_id: str,
    include_inactive: IncludeInactiveQuery = False,
    movie_service: MovieService = Depends(get_movie_service),
) -> ApiResponse[MovieRead]:
    """Return a single movie for public browsing."""
    movie = await movie_service.get_movie(movie_id, include_inactive=include_inactive)
    return ApiResponseFactory.success(data=movie, message="Movie loaded.")
