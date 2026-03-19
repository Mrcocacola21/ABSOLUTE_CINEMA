"""Simple observer implementation for domain events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class DomainEvent:
    """Base event produced by domain commands."""

    name: str
    payload: dict[str, object]
    occurred_at: datetime


@dataclass(slots=True)
class TicketPurchasedEvent(DomainEvent):
    """Event emitted when a ticket is purchased."""


@dataclass(slots=True)
class SessionCancelledEvent(DomainEvent):
    """Event emitted when a session is cancelled."""


class EventObserver(ABC):
    """Observer interface for reacting to domain events."""

    @abstractmethod
    async def notify(self, event: DomainEvent) -> None:
        """React to a published domain event."""


class LoggingEventObserver(EventObserver):
    """Observer that writes published events into the application log."""

    async def notify(self, event: DomainEvent) -> None:
        """Log an emitted event for auditing and future extensions."""
        logger.info("Domain event published: %s | payload=%s", event.name, event.payload)


class EventPublisher:
    """Event publisher maintaining a list of subscribed observers."""

    def __init__(self) -> None:
        self._observers: list[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        """Subscribe an observer to future events."""
        self._observers.append(observer)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all current observers."""
        for observer in self._observers:
            await observer.notify(event)


def build_default_event_publisher() -> EventPublisher:
    """Create the default in-process event publisher used by services."""
    publisher = EventPublisher()
    publisher.subscribe(LoggingEventObserver())
    return publisher


def new_ticket_purchased_event(payload: dict[str, object]) -> TicketPurchasedEvent:
    """Create a ticket purchased event instance."""
    return TicketPurchasedEvent(
        name="ticket_purchased",
        payload=payload,
        occurred_at=datetime.now(tz=timezone.utc),
    )


def new_session_cancelled_event(payload: dict[str, object]) -> SessionCancelledEvent:
    """Create a session cancelled event instance."""
    return SessionCancelledEvent(
        name="session_cancelled",
        payload=payload,
        occurred_at=datetime.now(tz=timezone.utc),
    )
