"""Unit tests for order aggregate refresh behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.commands.order_aggregate_refresh import refresh_order_aggregate
from app.core.constants import OrderStatuses, TicketStatuses
from app.core.exceptions import DatabaseException


class FakeOrderRepository:
    """Small repository double for aggregate refresh tests."""

    def __init__(self, order: dict[str, object] | None, *, update_returns_none: bool = False) -> None:
        self.order = order
        self.update_returns_none = update_returns_none
        self.update_calls: list[dict[str, object]] = []

    async def get_by_id(self, order_id: str, *, db_session=None) -> dict[str, object] | None:
        _ = db_session
        if self.order is None or self.order["id"] != order_id:
            return None
        return dict(self.order)

    async def update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = db_session
        self.update_calls.append(
            {
                "order_id": order_id,
                "updates": updates,
                "updated_at": updated_at,
            }
        )
        if self.update_returns_none or self.order is None:
            return None
        self.order = {
            **self.order,
            **updates,
            "updated_at": updated_at,
        }
        return dict(self.order)


class FakeTicketRepository:
    """Small repository double for ticket aggregate inputs."""

    def __init__(self, tickets: list[dict[str, object]]) -> None:
        self.tickets = tickets

    async def list_by_order(self, order_id: str, *, db_session=None) -> list[dict[str, object]]:
        _ = db_session
        return [ticket for ticket in self.tickets if ticket["order_id"] == order_id]


def build_order(
    *,
    status: str = OrderStatuses.COMPLETED,
    tickets_count: int = 2,
    total_price: float = 400.0,
) -> dict[str, object]:
    return {
        "id": "order-1",
        "status": status,
        "tickets_count": tickets_count,
        "total_price": total_price,
    }


def build_ticket(ticket_id: str, *, status: str, price: float = 200.0) -> dict[str, object]:
    return {
        "id": ticket_id,
        "order_id": "order-1",
        "status": status,
        "price": price,
    }


@pytest.mark.asyncio
async def test_refresh_order_aggregate_returns_existing_order_when_aggregate_is_current() -> None:
    order_repository = FakeOrderRepository(build_order())
    ticket_repository = FakeTicketRepository(
        [
            build_ticket("ticket-1", status=TicketStatuses.PURCHASED),
            build_ticket("ticket-2", status=TicketStatuses.PURCHASED),
        ]
    )

    refreshed = await refresh_order_aggregate(
        "order-1",
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        updated_at=datetime.now(tz=timezone.utc),
        db_session=object(),
    )

    assert refreshed == build_order()
    assert order_repository.update_calls == []


@pytest.mark.parametrize(
    ("ticket_statuses", "expected_status"),
    [
        ([TicketStatuses.PURCHASED, TicketStatuses.CANCELLED], OrderStatuses.PARTIALLY_CANCELLED),
        ([TicketStatuses.CANCELLED, TicketStatuses.CANCELLED], OrderStatuses.CANCELLED),
    ],
)
@pytest.mark.asyncio
async def test_refresh_order_aggregate_persists_ticket_derived_status(
    ticket_statuses: list[str],
    expected_status: str,
) -> None:
    updated_at = datetime.now(tz=timezone.utc)
    order_repository = FakeOrderRepository(build_order(status=OrderStatuses.COMPLETED))
    ticket_repository = FakeTicketRepository(
        [
            build_ticket("ticket-1", status=ticket_statuses[0]),
            build_ticket("ticket-2", status=ticket_statuses[1]),
        ]
    )

    refreshed = await refresh_order_aggregate(
        "order-1",
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        updated_at=updated_at,
        db_session=object(),
    )

    assert refreshed["status"] == expected_status
    assert order_repository.update_calls == [
        {
            "order_id": "order-1",
            "updates": {"status": expected_status},
            "updated_at": updated_at,
        }
    ]


@pytest.mark.asyncio
async def test_refresh_order_aggregate_updates_count_and_total_from_tickets() -> None:
    order_repository = FakeOrderRepository(build_order(tickets_count=1, total_price=200.0))
    ticket_repository = FakeTicketRepository(
        [
            build_ticket("ticket-1", status=TicketStatuses.PURCHASED, price=150.0),
            build_ticket("ticket-2", status=TicketStatuses.PURCHASED, price=175.0),
            build_ticket("ticket-3", status=TicketStatuses.PURCHASED, price=200.0),
        ]
    )

    refreshed = await refresh_order_aggregate(
        "order-1",
        order_repository=order_repository,
        ticket_repository=ticket_repository,
        updated_at=datetime.now(tz=timezone.utc),
        db_session=object(),
    )

    assert refreshed["tickets_count"] == 3
    assert refreshed["total_price"] == 525.0
    assert order_repository.update_calls[0]["updates"] == {
        "tickets_count": 3,
        "total_price": 525.0,
    }


@pytest.mark.asyncio
async def test_refresh_order_aggregate_rejects_missing_order() -> None:
    with pytest.raises(DatabaseException, match="Order for this operation was not found."):
        await refresh_order_aggregate(
            "missing-order",
            order_repository=FakeOrderRepository(None),
            ticket_repository=FakeTicketRepository([]),
            updated_at=datetime.now(tz=timezone.utc),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_refresh_order_aggregate_rejects_orders_without_tickets() -> None:
    with pytest.raises(DatabaseException, match="no tickets were found"):
        await refresh_order_aggregate(
            "order-1",
            order_repository=FakeOrderRepository(build_order()),
            ticket_repository=FakeTicketRepository([]),
            updated_at=datetime.now(tz=timezone.utc),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_refresh_order_aggregate_reports_failed_update() -> None:
    with pytest.raises(DatabaseException, match="could not be updated"):
        await refresh_order_aggregate(
            "order-1",
            order_repository=FakeOrderRepository(
                build_order(status=OrderStatuses.COMPLETED),
                update_returns_none=True,
            ),
            ticket_repository=FakeTicketRepository(
                [
                    build_ticket("ticket-1", status=TicketStatuses.CANCELLED),
                    build_ticket("ticket-2", status=TicketStatuses.CANCELLED),
                ]
            ),
            updated_at=datetime.now(tz=timezone.utc),
            db_session=object(),
        )
