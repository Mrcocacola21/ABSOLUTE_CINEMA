"""Unit tests for order validation tokens and PDF generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.builders.order_pdf import build_order_pdf
from app.schemas.localization import LocalizedText
from app.schemas.order import OrderDetailsRead, OrderTicketRead
from app.security.order_validation import create_order_validation_token, decode_order_validation_token


def test_order_validation_token_round_trip() -> None:
    order_id = "6803a522e5d4c4d94e7e1a10"

    token = create_order_validation_token(order_id)
    payload = decode_order_validation_token(token)

    assert payload is not None
    assert payload.sub == order_id
    assert payload.typ == "order_validation"
    assert decode_order_validation_token("not-a-token") is None


def test_order_pdf_builder_returns_pdf_bytes() -> None:
    now = datetime.now(tz=timezone.utc)
    order = OrderDetailsRead(
        id="6803a522e5d4c4d94e7e1a10",
        user_id="6803a522e5d4c4d94e7e1a11",
        session_id="6803a522e5d4c4d94e7e1a12",
        status="completed",
        total_price=420,
        tickets_count=2,
        created_at=now,
        updated_at=None,
        movie_id="6803a522e5d4c4d94e7e1a13",
        movie_title=LocalizedText(uk="PDF Test Movie", en="PDF Test Movie"),
        poster_url=None,
        age_rating="PG-13",
        session_start_time=now + timedelta(days=1),
        session_end_time=now + timedelta(days=1, hours=2),
        session_price=210,
        session_status="scheduled",
        active_tickets_count=2,
        cancelled_tickets_count=0,
        checked_in_tickets_count=0,
        unchecked_active_tickets_count=2,
        tickets=[
            OrderTicketRead(
                id="6803a522e5d4c4d94e7e1a20",
                order_id="6803a522e5d4c4d94e7e1a10",
                seat_row=1,
                seat_number=1,
                price=210,
                status="purchased",
                purchased_at=now,
                updated_at=None,
                cancelled_at=None,
                checked_in_at=None,
                is_cancellable=True,
                valid_for_entry=True,
            ),
            OrderTicketRead(
                id="6803a522e5d4c4d94e7e1a21",
                order_id="6803a522e5d4c4d94e7e1a10",
                seat_row=1,
                seat_number=2,
                price=210,
                status="purchased",
                purchased_at=now,
                updated_at=None,
                cancelled_at=None,
                checked_in_at=None,
                is_cancellable=True,
                valid_for_entry=True,
            ),
        ],
        valid_for_entry=True,
        entry_status_code="valid",
        entry_status_message="The order has active purchased tickets for a future scheduled session.",
        validation_token=create_order_validation_token("6803a522e5d4c4d94e7e1a10"),
        validation_url="http://localhost:5173/admin/order-validation/demo-token",
    )

    pdf_bytes = build_order_pdf(order=order, generated_at=now)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
