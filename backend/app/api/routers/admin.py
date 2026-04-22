"""Administrative API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from app.api.dependencies.auth import get_current_admin
from app.api.docs import (
    AUTHENTICATION_ERROR_RESPONSE,
    AUTHORIZATION_ERROR_RESPONSE,
    CONFLICT_ERROR_RESPONSE,
    NOT_FOUND_ERROR_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
    merge_openapi_responses,
)
from app.api.dependencies.services import get_admin_service, get_ticket_service, get_user_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.common import DeleteResultRead
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate
from app.schemas.report import AttendanceReportRead, AttendanceSessionDetailsRead
from app.schemas.session import (
    SessionBatchCreate,
    SessionBatchCreateRead,
    SessionCreate,
    SessionDetailsRead,
    SessionRead,
    SessionUpdate,
)
from app.schemas.ticket import TicketListRead
from app.schemas.user import UserRead
from app.services.admin import AdminService
from app.services.ticket import TicketService
from app.services.user import UserService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses=merge_openapi_responses(AUTHENTICATION_ERROR_RESPONSE, AUTHORIZATION_ERROR_RESPONSE),
)

MovieCreatePayload = Annotated[
    MovieCreate,
    Body(
        openapi_examples={
            "localized_movie": {
                "summary": "Localized movie ready for scheduling",
                "value": {
                    "title": {"uk": "Інтерстеллар", "en": "Interstellar"},
                    "description": {
                        "uk": "Науково-фантастична драма про подорож крізь час і простір.",
                        "en": "A science-fiction drama about travel through time and space.",
                    },
                    "duration_minutes": 169,
                    "poster_url": "https://example.com/posters/interstellar.jpg",
                    "age_rating": "PG-13",
                    "genres": ["science_fiction", "drama"],
                    "status": "planned",
                },
            }
        }
    ),
]

MovieUpdatePayload = Annotated[
    MovieUpdate,
    Body(
        openapi_examples={
            "localized_partial_update": {
                "summary": "Update poster and English copy",
                "value": {
                    "description": {"en": "Updated English description for the current demo build."},
                    "poster_url": "/demo-posters/interstellar.svg",
                    "genres": ["science_fiction", "drama"],
                },
            }
        }
    ),
]

SessionCreatePayload = Annotated[
    SessionCreate,
    Body(
        openapi_examples={
            "single_session": {
                "summary": "Create one future screening",
                "value": {
                    "movie_id": "6803a522e5d4c4d94e7e1a10",
                    "start_time": "2026-04-22T18:00:00+03:00",
                    "end_time": "2026-04-22T21:00:00+03:00",
                    "price": 220,
                },
            }
        }
    ),
]

SessionBatchCreatePayload = Annotated[
    SessionBatchCreate,
    Body(
        openapi_examples={
            "batch_session": {
                "summary": "Create the same slot on multiple dates",
                "value": {
                    "movie_id": "6803a522e5d4c4d94e7e1a10",
                    "start_time": "2026-04-22T18:00:00+03:00",
                    "end_time": "2026-04-22T21:00:00+03:00",
                    "price": 220,
                    "dates": ["2026-04-22", "2026-04-23", "2026-04-24"],
                },
            }
        }
    ),
]

SessionUpdatePayload = Annotated[
    SessionUpdate,
    Body(
        openapi_examples={
            "session_update": {
                "summary": "Move the start time and adjust the price",
                "value": {
                    "start_time": "2026-04-22T19:00:00+03:00",
                    "end_time": "2026-04-22T22:00:00+03:00",
                    "price": 240,
                },
            }
        }
    ),
]


@router.get(
    "/movies",
    response_model=ApiResponse[list[MovieRead]],
    summary="List admin movies",
    description="Return all movies visible in the administrator workspace, including planned and deactivated titles.",
    response_description="Wrapped list of movies for the admin board.",
)
async def list_movies(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[list[MovieRead]]:
    """Return all movies for the admin movie board."""
    movies = await admin_service.list_movies(requested_by=admin_user)
    return ApiResponseFactory.success(data=movies, message="Admin movies loaded.")


@router.get(
    "/movies/{movie_id}",
    response_model=ApiResponse[MovieRead],
    summary="Get one admin movie",
    description="Return one movie record for the admin workspace.",
    response_description="Wrapped movie record for admin use.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def get_movie(
    movie_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Return one movie for the admin board."""
    movie = await admin_service.get_movie(movie_id=movie_id, requested_by=admin_user)
    return ApiResponseFactory.success(data=movie, message="Admin movie loaded.")


@router.post(
    "/movies",
    response_model=ApiResponse[MovieRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a movie",
    description="Create a localized movie entry that can later be placed into the cinema schedule.",
    response_description="Wrapped created movie record.",
    responses=VALIDATION_ERROR_RESPONSE,
)
async def create_movie(
    payload: MovieCreatePayload,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Create a movie record that can later be added to the schedule."""
    movie = await admin_service.create_movie(payload=payload, created_by=admin_user)
    return ApiResponseFactory.created(data=movie, message="Movie created successfully.")


@router.patch(
    "/movies/{movie_id}",
    response_model=ApiResponse[MovieRead],
    summary="Update a movie",
    description="Edit localized movie metadata, artwork, genres, or lifecycle status from the admin workspace.",
    response_description="Wrapped updated movie record.",
    responses=merge_openapi_responses(
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def update_movie(
    movie_id: str,
    payload: MovieUpdatePayload,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Update movie information managed by administrators."""
    movie = await admin_service.update_movie(movie_id=movie_id, payload=payload, updated_by=admin_user)
    return ApiResponseFactory.success(data=movie, message="Movie updated successfully.")


@router.patch(
    "/movies/{movie_id}/deactivate",
    response_model=ApiResponse[MovieRead],
    summary="Deactivate a movie",
    description="Soft-disable a movie while preserving historical session and ticket references.",
    response_description="Wrapped deactivated movie record.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, CONFLICT_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def deactivate_movie(
    movie_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Soft-disable a movie while preserving historical references."""
    movie = await admin_service.deactivate_movie(movie_id=movie_id, deactivated_by=admin_user)
    return ApiResponseFactory.success(data=movie, message="Movie deactivated successfully.")


@router.delete(
    "/movies/{movie_id}",
    response_model=ApiResponse[DeleteResultRead],
    summary="Delete a movie",
    description="Delete a movie only when it has never been used by any session.",
    response_description="Wrapped delete result.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, CONFLICT_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def delete_movie(
    movie_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[DeleteResultRead]:
    """Delete a movie when it is safe to do so."""
    result = await admin_service.delete_movie(movie_id=movie_id, deleted_by=admin_user)
    return ApiResponseFactory.success(data=result, message="Movie deleted successfully.")


@router.get(
    "/sessions",
    response_model=ApiResponse[list[SessionDetailsRead]],
    summary="List admin sessions",
    description="Return all sessions shown in the admin schedule board.",
    response_description="Wrapped list of admin session records.",
)
async def list_sessions(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[list[SessionDetailsRead]]:
    """Return all sessions for the admin schedule board."""
    sessions = await admin_service.list_sessions(requested_by=admin_user)
    return ApiResponseFactory.success(data=sessions, message="Admin sessions loaded.")


@router.get(
    "/sessions/{session_id}",
    response_model=ApiResponse[SessionDetailsRead],
    summary="Get one admin session",
    description="Return one session record together with its nested movie details for the admin board.",
    response_description="Wrapped admin session details.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def get_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionDetailsRead]:
    """Return one session for the admin board."""
    session = await admin_service.get_session(session_id=session_id, requested_by=admin_user)
    return ApiResponseFactory.success(data=session, message="Admin session loaded.")


@router.post(
    "/sessions",
    response_model=ApiResponse[SessionDetailsRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a session",
    description="Create one future screening for a movie in the one-hall cinema schedule.",
    response_description="Wrapped created session details.",
    responses=merge_openapi_responses(CONFLICT_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def create_session(
    payload: SessionCreatePayload,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionDetailsRead]:
    """Create a new movie session for the schedule."""
    session = await admin_service.create_session(payload=payload, created_by=admin_user)
    return ApiResponseFactory.created(data=session, message="Session created successfully.")


@router.post(
    "/sessions/batch",
    response_model=ApiResponse[SessionBatchCreateRead],
    summary="Create a batch of sessions",
    description="Create the same screening slot on multiple calendar dates and return both created and rejected entries.",
    response_description="Wrapped batch session planning result.",
    responses=VALIDATION_ERROR_RESPONSE,
)
async def create_sessions_batch(
    payload: SessionBatchCreatePayload,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionBatchCreateRead]:
    """Create the same session slot across multiple selected dates."""
    result = await admin_service.create_sessions_batch(payload=payload, created_by=admin_user)
    return ApiResponseFactory.success(data=result, message="Batch session planning processed.")


@router.patch(
    "/sessions/{session_id}",
    response_model=ApiResponse[SessionDetailsRead],
    summary="Update a session",
    description="Edit a future session that is still allowed to change under the current business rules.",
    response_description="Wrapped updated session details.",
    responses=merge_openapi_responses(
        NOT_FOUND_ERROR_RESPONSE,
        CONFLICT_ERROR_RESPONSE,
        VALIDATION_ERROR_RESPONSE,
    ),
)
async def update_session(
    session_id: str,
    payload: SessionUpdatePayload,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionDetailsRead]:
    """Update an existing session."""
    session = await admin_service.update_session(
        session_id=session_id,
        payload=payload,
        updated_by=admin_user,
    )
    return ApiResponseFactory.success(data=session, message="Session updated successfully.")


@router.patch(
    "/sessions/{session_id}/cancel",
    response_model=ApiResponse[SessionRead],
    summary="Cancel a session",
    description="Cancel a scheduled session and propagate the cancellation rules to downstream ticket and order flows.",
    response_description="Wrapped cancelled session record.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, CONFLICT_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def cancel_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionRead]:
    """Cancel an existing movie session."""
    session = await admin_service.cancel_session(session_id=session_id, cancelled_by=admin_user)
    return ApiResponseFactory.success(data=session, message="Session cancelled successfully.")


@router.delete(
    "/sessions/{session_id}",
    response_model=ApiResponse[DeleteResultRead],
    summary="Delete a session",
    description="Delete a session only when no ticket history exists for that screening.",
    response_description="Wrapped delete result.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, CONFLICT_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def delete_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[DeleteResultRead]:
    """Delete a session when it is safe to do so."""
    result = await admin_service.delete_session(session_id=session_id, deleted_by=admin_user)
    return ApiResponseFactory.success(data=result, message="Session deleted successfully.")


@router.get(
    "/tickets",
    response_model=ApiResponse[list[TicketListRead]],
    summary="List admin tickets",
    description="Return all tickets visible in the admin workspace.",
    response_description="Wrapped list of admin ticket records.",
)
async def list_tickets(
    admin_user: UserRead = Depends(get_current_admin),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> ApiResponse[list[TicketListRead]]:
    """Return all tickets for admin views."""
    tickets = await ticket_service.list_admin_tickets(requested_by=admin_user)
    return ApiResponseFactory.success(data=tickets, message="Admin tickets loaded.")


@router.get(
    "/users",
    response_model=ApiResponse[list[UserRead]],
    summary="List users",
    description="Return all user accounts for the administrator workspace.",
    response_description="Wrapped list of user profiles.",
)
async def list_users(
    admin_user: UserRead = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[list[UserRead]]:
    """Return all users for admin views."""
    users = await user_service.list_users(requested_by=admin_user)
    return ApiResponseFactory.success(data=users, message="Admin users loaded.")


@router.get(
    "/attendance",
    response_model=ApiResponse[AttendanceReportRead],
    summary="Get the attendance report",
    description="Build the attendance summary used by the admin reporting workspace.",
    response_description="Wrapped attendance report.",
)
async def get_attendance(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[AttendanceReportRead]:
    """Build an attendance report for administrators."""
    report = await admin_service.build_attendance_report(requested_by=admin_user)
    return ApiResponseFactory.success(data=report, message="Attendance report generated.")


@router.get(
    "/attendance/sessions/{session_id}",
    response_model=ApiResponse[AttendanceSessionDetailsRead],
    summary="Get attendance details for one session",
    description="Return the seat map, occupancy, and ticket details for one session in the attendance report.",
    response_description="Wrapped attendance details for a single session.",
    responses=merge_openapi_responses(NOT_FOUND_ERROR_RESPONSE, VALIDATION_ERROR_RESPONSE),
)
async def get_attendance_session_details(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[AttendanceSessionDetailsRead]:
    """Return detailed attendance information for one session."""
    details = await admin_service.get_attendance_session_details(session_id=session_id, requested_by=admin_user)
    return ApiResponseFactory.success(data=details, message="Attendance session details loaded.")
