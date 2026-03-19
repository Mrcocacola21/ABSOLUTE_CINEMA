"""Administrative API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_admin
from app.api.dependencies.services import get_admin_service
from app.core.responses import ApiResponse
from app.factories.response_factory import ApiResponseFactory
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate
from app.schemas.report import AttendanceReportRead
from app.schemas.session import SessionCreate, SessionDetailsRead, SessionRead
from app.schemas.user import UserRead
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/movies", response_model=ApiResponse[list[MovieRead]])
async def list_movies(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[list[MovieRead]]:
    """Return all movies for the admin movie board."""
    movies = await admin_service.list_movies(requested_by=admin_user)
    return ApiResponseFactory.success(data=movies, message="Admin movies loaded.")


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


@router.get("/sessions", response_model=ApiResponse[list[SessionDetailsRead]])
async def list_sessions(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[list[SessionDetailsRead]]:
    """Return all sessions for the admin schedule board."""
    sessions = await admin_service.list_sessions(requested_by=admin_user)
    return ApiResponseFactory.success(data=sessions, message="Admin sessions loaded.")


@router.post("/sessions", response_model=ApiResponse[SessionDetailsRead], status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionDetailsRead]:
    """Create a new movie session for the schedule."""
    session = await admin_service.create_session(payload=payload, created_by=admin_user)
    return ApiResponseFactory.created(data=session, message="Session created successfully.")


@router.patch("/sessions/{session_id}/cancel", response_model=ApiResponse[SessionRead])
async def cancel_session(
    session_id: str,
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[SessionRead]:
    """Cancel an existing movie session."""
    session = await admin_service.cancel_session(session_id=session_id, cancelled_by=admin_user)
    return ApiResponseFactory.success(data=session, message="Session cancelled successfully.")


@router.get("/attendance", response_model=ApiResponse[AttendanceReportRead])
async def get_attendance(
    admin_user: UserRead = Depends(get_current_admin),
    admin_service: AdminService = Depends(get_admin_service),
) -> ApiResponse[AttendanceReportRead]:
    """Build an attendance report for administrators."""
    report = await admin_service.build_attendance_report(requested_by=admin_user)
    return ApiResponseFactory.success(data=report, message="Attendance report generated.")
