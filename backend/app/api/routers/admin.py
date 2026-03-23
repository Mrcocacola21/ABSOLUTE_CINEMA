"""Administrative API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_admin
from app.api.dependencies.services import get_admin_service, get_ticket_service, get_user_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.common import DeleteResultRead
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate
from app.schemas.report import AttendanceReportRead
from app.schemas.session import SessionCreate, SessionDetailsRead, SessionRead, SessionUpdate
from app.schemas.ticket import TicketListRead
from app.schemas.user import UserRead
from app.services.admin import AdminService
from app.services.ticket import TicketService
from app.services.user import UserService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/movies", response_model=ApiResponse[list[MovieRead]])
async def list_movies(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[list[MovieRead]]:
    """Return all movies for the admin movie board."""
    movies = await admin_service.list_movies(requested_by=admin_user)
    return ApiResponseFactory.success(data=movies, message="Admin movies loaded.")


@router.get("/movies/{movie_id}", response_model=ApiResponse[MovieRead])
async def get_movie(
    movie_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Return one movie for the admin board."""
    movie = await admin_service.get_movie(movie_id=movie_id, requested_by=admin_user)
    return ApiResponseFactory.success(data=movie, message="Admin movie loaded.")


@router.post("/movies", response_model=ApiResponse[MovieRead], status_code=status.HTTP_201_CREATED)
async def create_movie(
    payload: MovieCreate,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Create a movie record that can later be added to the schedule."""
    movie = await admin_service.create_movie(payload=payload, created_by=admin_user)
    return ApiResponseFactory.created(data=movie, message="Movie created successfully.")


@router.patch("/movies/{movie_id}", response_model=ApiResponse[MovieRead])
async def update_movie(
    movie_id: str,
    payload: MovieUpdate,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Update movie information managed by administrators."""
    movie = await admin_service.update_movie(movie_id=movie_id, payload=payload, updated_by=admin_user)
    return ApiResponseFactory.success(data=movie, message="Movie updated successfully.")


@router.patch("/movies/{movie_id}/deactivate", response_model=ApiResponse[MovieRead])
async def deactivate_movie(
    movie_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[MovieRead]:
    """Soft-disable a movie while preserving historical references."""
    movie = await admin_service.deactivate_movie(movie_id=movie_id, deactivated_by=admin_user)
    return ApiResponseFactory.success(data=movie, message="Movie deactivated successfully.")


@router.delete("/movies/{movie_id}", response_model=ApiResponse[DeleteResultRead])
async def delete_movie(
    movie_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[DeleteResultRead]:
    """Delete a movie when it is safe to do so."""
    result = await admin_service.delete_movie(movie_id=movie_id, deleted_by=admin_user)
    return ApiResponseFactory.success(data=result, message="Movie deleted successfully.")


@router.get("/sessions", response_model=ApiResponse[list[SessionDetailsRead]])
async def list_sessions(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[list[SessionDetailsRead]]:
    """Return all sessions for the admin schedule board."""
    sessions = await admin_service.list_sessions(requested_by=admin_user)
    return ApiResponseFactory.success(data=sessions, message="Admin sessions loaded.")


@router.get("/sessions/{session_id}", response_model=ApiResponse[SessionDetailsRead])
async def get_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionDetailsRead]:
    """Return one session for the admin board."""
    session = await admin_service.get_session(session_id=session_id, requested_by=admin_user)
    return ApiResponseFactory.success(data=session, message="Admin session loaded.")


@router.post("/sessions", response_model=ApiResponse[SessionDetailsRead], status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionDetailsRead]:
    """Create a new movie session for the schedule."""
    session = await admin_service.create_session(payload=payload, created_by=admin_user)
    return ApiResponseFactory.created(data=session, message="Session created successfully.")


@router.patch("/sessions/{session_id}", response_model=ApiResponse[SessionDetailsRead])
async def update_session(
    session_id: str,
    payload: SessionUpdate,
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


@router.patch("/sessions/{session_id}/cancel", response_model=ApiResponse[SessionRead])
async def cancel_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionRead]:
    """Cancel an existing movie session."""
    session = await admin_service.cancel_session(session_id=session_id, cancelled_by=admin_user)
    return ApiResponseFactory.success(data=session, message="Session cancelled successfully.")


@router.delete("/sessions/{session_id}", response_model=ApiResponse[DeleteResultRead])
async def delete_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[DeleteResultRead]:
    """Delete a session when it is safe to do so."""
    result = await admin_service.delete_session(session_id=session_id, deleted_by=admin_user)
    return ApiResponseFactory.success(data=result, message="Session deleted successfully.")


@router.get("/tickets", response_model=ApiResponse[list[TicketListRead]])
async def list_tickets(
    admin_user: UserRead = Depends(get_current_admin),
    ticket_service: TicketService = Depends(get_ticket_service),
) -> ApiResponse[list[TicketListRead]]:
    """Return all tickets for admin views."""
    tickets = await ticket_service.list_admin_tickets(requested_by=admin_user)
    return ApiResponseFactory.success(data=tickets, message="Admin tickets loaded.")


@router.get("/users", response_model=ApiResponse[list[UserRead]])
async def list_users(
    admin_user: UserRead = Depends(get_current_admin),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[list[UserRead]]:
    """Return all users for admin views."""
    users = await user_service.list_users(requested_by=admin_user)
    return ApiResponseFactory.success(data=users, message="Admin users loaded.")


@router.get("/attendance", response_model=ApiResponse[AttendanceReportRead])
async def get_attendance(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[AttendanceReportRead]:
    """Build an attendance report for administrators."""
    report = await admin_service.build_attendance_report(requested_by=admin_user)
    return ApiResponseFactory.success(data=report, message="Attendance report generated.")
