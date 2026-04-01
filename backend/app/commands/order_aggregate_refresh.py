"""Shared helper for refreshing stored order aggregates from nested tickets."""

from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.core.exceptions import DatabaseException
from app.repositories.orders import OrderRepository
from app.repositories.tickets import TicketRepository
from app.utils.order_aggregates import build_order_aggregate_updates


async def refresh_order_aggregate(
    order_id: str,
    *,
    order_repository: OrderRepository,
    ticket_repository: TicketRepository,
    updated_at: datetime,
    db_session: AsyncIOMotorClientSession,
) -> dict[str, object]:
    """Recompute an order aggregate from its tickets and persist any changes."""
    order_document = await order_repository.get_by_id(order_id, db_session=db_session)
    if order_document is None:
        raise DatabaseException("Order for this operation was not found.")

    ticket_documents = await ticket_repository.list_by_order(order_id, db_session=db_session)
    if not ticket_documents:
        raise DatabaseException("Order aggregate could not be refreshed because no tickets were found.")

    updates = build_order_aggregate_updates(
        order_document=order_document,
        ticket_documents=ticket_documents,
    )
    if not updates:
        return order_document

    updated_order = await order_repository.update_order(
        order_id,
        updates=updates,
        updated_at=updated_at,
        db_session=db_session,
    )
    if updated_order is None:
        raise DatabaseException("Order aggregate could not be updated.")
    return updated_order
