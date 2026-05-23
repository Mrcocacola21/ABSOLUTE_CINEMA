"""MongoDB collection naming conventions."""


class DatabaseCollections:
    """Centralized collection names for MongoDB access."""

    USERS = "users"
    MOVIES = "movies"
    SESSIONS = "sessions"
    ORDERS = "orders"
    TICKETS = "tickets"
    PAYMENTS = "payments"
    PAYMENT_ATTEMPTS = "payment_attempts"
    PAYMENT_WEBHOOK_EVENTS = "payment_webhook_events"
    PAYMENT_AUDIT_EVENTS = "payment_audit_events"
    REFUNDS = "refunds"
