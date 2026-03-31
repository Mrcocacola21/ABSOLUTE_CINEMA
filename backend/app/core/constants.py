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

    PURCHASED = "purchased"
    CANCELLED = "cancelled"


MOVIE_STATUS_VALUES: Final[tuple[str, ...]] = (
    MovieStatuses.PLANNED,
    MovieStatuses.ACTIVE,
    MovieStatuses.DEACTIVATED,
)
ALLOWED_SORT_FIELDS: Final[tuple[str, ...]] = (
    "movie_title",
    "available_seats",
    "start_time",
)
ALLOWED_SORT_ORDERS: Final[tuple[str, ...]] = ("asc", "desc")
