"""Dependency providers for repositories and services."""

from app.repositories.movies import MovieRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.services.admin import AdminService
from app.services.auth import AuthService
from app.services.movie import MovieService
from app.services.schedule import ScheduleService
from app.services.ticket import TicketService
from app.services.user import UserService


def get_user_repository() -> UserRepository:
    """Create a user repository instance."""
    return UserRepository()


def get_movie_repository() -> MovieRepository:
    """Create a movie repository instance."""
    return MovieRepository()


def get_session_repository() -> SessionRepository:
    """Create a session repository instance."""
    return SessionRepository()


def get_ticket_repository() -> TicketRepository:
    """Create a ticket repository instance."""
    return TicketRepository()


def get_auth_service() -> AuthService:
    """Create an authentication service instance."""
    return AuthService(
        user_repository=get_user_repository(),
    )


def get_user_service() -> UserService:
    """Create a user service instance."""
    return UserService(
        user_repository=get_user_repository(),
    )


def get_movie_service() -> MovieService:
    """Create a public movie service instance."""
    return MovieService(
        movie_repository=get_movie_repository(),
    )


def get_schedule_service() -> ScheduleService:
    """Create a schedule browsing service instance."""
    return ScheduleService(
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
        movie_repository=get_movie_repository(),
    )


def get_ticket_service() -> TicketService:
    """Create a ticket service instance."""
    return TicketService(
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
    )


def get_admin_service() -> AdminService:
    """Create an administration service instance."""
    return AdminService(
        movie_repository=get_movie_repository(),
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
    )
