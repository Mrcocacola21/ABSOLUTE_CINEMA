"""Helpers for deriving order aggregate fields from nested tickets."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import OrderStatuses, TicketStatuses


@dataclass(frozen=True, slots=True)
class OrderAggregateSnapshot:
    """Derived aggregate values for one order."""

    status: str
    tickets_count: int
    total_price: float
    active_tickets_count: int


def build_order_aggregate_snapshot(ticket_documents: list[dict[str, object]]) -> OrderAggregateSnapshot:
    """Compute the stored order aggregate from nested ticket documents."""
    active_tickets_count = sum(
        1 for ticket in ticket_documents if ticket["status"] == TicketStatuses.PURCHASED
    )
    if active_tickets_count <= 0:
        status = OrderStatuses.CANCELLED
    elif active_tickets_count == len(ticket_documents):
        status = OrderStatuses.COMPLETED
    else:
        status = OrderStatuses.PARTIALLY_CANCELLED

    return OrderAggregateSnapshot(
        status=status,
        tickets_count=len(ticket_documents),
        total_price=float(sum(float(ticket["price"]) for ticket in ticket_documents)),
        active_tickets_count=active_tickets_count,
    )


def build_order_aggregate_updates(
    *,
    order_document: dict[str, object],
    ticket_documents: list[dict[str, object]],
) -> dict[str, object]:
    """Return only the order fields that differ from the derived ticket aggregate."""
    aggregate = build_order_aggregate_snapshot(ticket_documents)
    updates: dict[str, object] = {}

    if order_document.get("status") != aggregate.status:
        updates["status"] = aggregate.status
    if int(order_document.get("tickets_count", 0)) != aggregate.tickets_count:
        updates["tickets_count"] = aggregate.tickets_count
    if float(order_document.get("total_price", 0)) != aggregate.total_price:
        updates["total_price"] = aggregate.total_price

    return updates
