"""Dependency providers for repositories and services."""

from app.repositories.movies import MovieRepository
from app.repositories.orders import OrderRepository
from app.repositories.payment_attempts import PaymentAttemptRepository
from app.repositories.payment_audit_events import PaymentAuditEventRepository
from app.repositories.payment_webhook_events import PaymentWebhookEventRepository
from app.repositories.payments import PaymentRepository
from app.repositories.refunds import RefundRepository
from app.repositories.sessions import SessionRepository
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.payments.providers.base import PaymentProvider
from app.payments.providers.factory import build_payment_provider
from app.services.admin import AdminService
from app.services.auth import AuthService
from app.services.movie import MovieService
from app.services.order import OrderService
from app.services.payment import PaymentService
from app.services.refund import RefundService
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


def get_order_repository() -> OrderRepository:
    """Create an order repository instance."""
    return OrderRepository()


def get_ticket_repository() -> TicketRepository:
    """Create a ticket repository instance."""
    return TicketRepository()


def get_payment_repository() -> PaymentRepository:
    """Create a payment repository instance."""
    return PaymentRepository()


def get_payment_attempt_repository() -> PaymentAttemptRepository:
    """Create a payment attempt repository instance."""
    return PaymentAttemptRepository()


def get_payment_webhook_event_repository() -> PaymentWebhookEventRepository:
    """Create a payment webhook event repository instance."""
    return PaymentWebhookEventRepository()


def get_payment_audit_event_repository() -> PaymentAuditEventRepository:
    """Create a payment audit event repository instance."""
    return PaymentAuditEventRepository()


def get_refund_repository() -> RefundRepository:
    """Create a refund repository instance."""
    return RefundRepository()


def get_payment_provider() -> PaymentProvider:
    """Resolve the configured payment provider adapter."""
    return build_payment_provider()


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
        session_repository=get_session_repository(),
    )


def get_schedule_service() -> ScheduleService:
    """Create a schedule browsing service instance."""
    return ScheduleService(
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
        movie_repository=get_movie_repository(),
        order_repository=get_order_repository(),
        payment_repository=get_payment_repository(),
    )


def get_ticket_service() -> TicketService:
    """Create a ticket service instance."""
    return TicketService(
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
        order_repository=get_order_repository(),
        movie_repository=get_movie_repository(),
        user_repository=get_user_repository(),
        payment_repository=get_payment_repository(),
        refund_service=get_refund_service(),
    )


def get_order_service() -> OrderService:
    """Create an order service instance."""
    return OrderService(
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
        movie_repository=get_movie_repository(),
        order_repository=get_order_repository(),
        payment_repository=get_payment_repository(),
        refund_service=get_refund_service(),
    )


def get_payment_service() -> PaymentService:
    """Create a provider-neutral payment service instance."""
    return PaymentService(
        payment_repository=get_payment_repository(),
        payment_attempt_repository=get_payment_attempt_repository(),
        payment_webhook_event_repository=get_payment_webhook_event_repository(),
        payment_audit_event_repository=get_payment_audit_event_repository(),
        refund_repository=get_refund_repository(),
        order_repository=get_order_repository(),
        ticket_repository=get_ticket_repository(),
        session_repository=get_session_repository(),
        payment_provider=get_payment_provider(),
        user_repository=get_user_repository(),
        movie_repository=get_movie_repository(),
    )


def get_refund_service() -> RefundService:
    """Create a provider-neutral refund service instance."""
    return RefundService(
        refund_repository=get_refund_repository(),
        payment_repository=get_payment_repository(),
        payment_provider=get_payment_provider(),
        payment_audit_event_repository=get_payment_audit_event_repository(),
    )


def get_admin_service() -> AdminService:
    """Create an administration service instance."""
    return AdminService(
        movie_repository=get_movie_repository(),
        session_repository=get_session_repository(),
        ticket_repository=get_ticket_repository(),
        order_repository=get_order_repository(),
        user_repository=get_user_repository(),
        payment_repository=get_payment_repository(),
        refund_service=get_refund_service(),
    )
