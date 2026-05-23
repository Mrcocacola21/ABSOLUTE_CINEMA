"""Project-wide constants used across the backend."""

from typing import Final

API_V1_PREFIX: Final[str] = "/api/v1"
DEFAULT_PAGE_LIMIT: Final[int] = 20
MAX_PAGE_LIMIT: Final[int] = 100
DEFAULT_SORT_BY: Final[str] = "start_time"
DEFAULT_SORT_ORDER: Final[str] = "asc"


class Roles:
    """Available authorization roles."""

    USER = "user"
    ADMIN = "admin"


class MovieStatuses:
    """Lifecycle statuses for movies in the cinema catalog."""

    PLANNED = "planned"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class SessionStatuses:
    """Lifecycle statuses for movie sessions."""

    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TicketStatuses:
    """Lifecycle statuses for tickets."""

    RESERVED = "reserved"
    PURCHASED = "purchased"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OrderStatuses:
    """Lifecycle statuses for ticket purchase orders."""

    PENDING_PAYMENT = "pending_payment"
    COMPLETED = "completed"
    PARTIALLY_CANCELLED = "partially_cancelled"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_CANCELLED = "payment_cancelled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatuses:
    """Lifecycle statuses for payment aggregates."""

    CREATED = "created"
    PENDING = "pending"
    REQUIRES_ACTION = "requires_action"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentAttemptStatuses:
    """Lifecycle statuses for individual payment attempts."""

    CREATED = "created"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RefundStatuses:
    """Lifecycle statuses for payment refunds."""

    CREATED = "created"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentWebhookProcessingStatuses:
    """Processing statuses for received payment webhook events."""

    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


MOVIE_STATUS_VALUES: Final[tuple[str, ...]] = (
    MovieStatuses.PLANNED,
    MovieStatuses.ACTIVE,
    MovieStatuses.DEACTIVATED,
)
ORDER_STATUS_VALUES: Final[tuple[str, ...]] = (
    OrderStatuses.PENDING_PAYMENT,
    OrderStatuses.COMPLETED,
    OrderStatuses.PARTIALLY_CANCELLED,
    OrderStatuses.PAYMENT_FAILED,
    OrderStatuses.PAYMENT_CANCELLED,
    OrderStatuses.CANCELLED,
    OrderStatuses.EXPIRED,
)
TICKET_STATUS_VALUES: Final[tuple[str, ...]] = (
    TicketStatuses.RESERVED,
    TicketStatuses.PURCHASED,
    TicketStatuses.CANCELLED,
    TicketStatuses.EXPIRED,
)
TICKET_BLOCKING_STATUS_VALUES: Final[tuple[str, ...]] = (
    TicketStatuses.RESERVED,
    TicketStatuses.PURCHASED,
)
PAYMENT_STATUS_VALUES: Final[tuple[str, ...]] = (
    PaymentStatuses.CREATED,
    PaymentStatuses.PENDING,
    PaymentStatuses.REQUIRES_ACTION,
    PaymentStatuses.SUCCEEDED,
    PaymentStatuses.FAILED,
    PaymentStatuses.CANCELLED,
    PaymentStatuses.EXPIRED,
    PaymentStatuses.REFUNDED,
    PaymentStatuses.PARTIALLY_REFUNDED,
)
PAYMENT_ATTEMPT_STATUS_VALUES: Final[tuple[str, ...]] = (
    PaymentAttemptStatuses.CREATED,
    PaymentAttemptStatuses.PENDING,
    PaymentAttemptStatuses.SUCCEEDED,
    PaymentAttemptStatuses.FAILED,
)
REFUND_STATUS_VALUES: Final[tuple[str, ...]] = (
    RefundStatuses.CREATED,
    RefundStatuses.PENDING,
    RefundStatuses.SUCCEEDED,
    RefundStatuses.FAILED,
    RefundStatuses.CANCELLED,
)
PAYMENT_WEBHOOK_PROCESSING_STATUS_VALUES: Final[tuple[str, ...]] = (
    PaymentWebhookProcessingStatuses.RECEIVED,
    PaymentWebhookProcessingStatuses.PROCESSING,
    PaymentWebhookProcessingStatuses.PROCESSED,
    PaymentWebhookProcessingStatuses.FAILED,
    PaymentWebhookProcessingStatuses.SKIPPED,
)
ALLOWED_SORT_FIELDS: Final[tuple[str, ...]] = (
    "movie_title",
    "available_seats",
    "start_time",
)
ALLOWED_SORT_ORDERS: Final[tuple[str, ...]] = ("asc", "desc")
