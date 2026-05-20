"""Unit tests for order validation tokens and PDF generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

from app.builders import order_pdf
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


def build_pdf_order(
    *,
    now: datetime,
    tickets: list[OrderTicketRead] | None = None,
    valid_for_entry: bool = True,
    entry_status_code: str = "valid",
    entry_status_message: str = "The order has active purchased tickets for a future scheduled session.",
) -> OrderDetailsRead:
    effective_tickets = tickets or [
        build_pdf_ticket(
            "6803a522e5d4c4d94e7e1a20",
            now=now,
            seat_row=1,
            seat_number=1,
            valid_for_entry=True,
        ),
        build_pdf_ticket(
            "6803a522e5d4c4d94e7e1a21",
            now=now,
            seat_row=1,
            seat_number=2,
            valid_for_entry=True,
        ),
    ]
    active_tickets_count = sum(1 for ticket in effective_tickets if ticket.status == "purchased")
    cancelled_tickets_count = len(effective_tickets) - active_tickets_count
    checked_in_tickets_count = sum(
        1 for ticket in effective_tickets if ticket.status == "purchased" and ticket.checked_in_at is not None
    )
    return OrderDetailsRead(
        id="6803a522e5d4c4d94e7e1a10",
        user_id="6803a522e5d4c4d94e7e1a11",
        session_id="6803a522e5d4c4d94e7e1a12",
        status="partially_cancelled" if cancelled_tickets_count else "completed",
        total_price=sum(ticket.price for ticket in effective_tickets),
        tickets_count=len(effective_tickets),
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
        active_tickets_count=active_tickets_count,
        cancelled_tickets_count=cancelled_tickets_count,
        checked_in_tickets_count=checked_in_tickets_count,
        unchecked_active_tickets_count=max(active_tickets_count - checked_in_tickets_count, 0),
        tickets=effective_tickets,
        valid_for_entry=valid_for_entry,
        entry_status_code=entry_status_code,
        entry_status_message=entry_status_message,
        validation_token=create_order_validation_token("6803a522e5d4c4d94e7e1a10"),
        validation_url="http://localhost:5173/admin/order-validation/demo-token",
    )


def build_pdf_ticket(
    ticket_id: str,
    *,
    now: datetime,
    seat_row: int,
    seat_number: int,
    status: str = "purchased",
    checked_in_at: datetime | None = None,
    valid_for_entry: bool = True,
) -> OrderTicketRead:
    return OrderTicketRead(
        id=ticket_id,
        order_id="6803a522e5d4c4d94e7e1a10",
        seat_row=seat_row,
        seat_number=seat_number,
        price=210,
        status=status,
        purchased_at=now,
        updated_at=None,
        cancelled_at=(now + timedelta(minutes=5)) if status == "cancelled" else None,
        checked_in_at=checked_in_at,
        is_cancellable=False,
        valid_for_entry=valid_for_entry,
    )


class RecordingCanvas:
    def __init__(self, buffer: BytesIO, *, pagesize: tuple[float, float]) -> None:
        self.buffer = buffer
        self.pagesize = pagesize
        self.text: list[str] = []
        self.page_breaks = 0

    def setFillColor(self, *_: object) -> None:
        pass

    def setStrokeColor(self, *_: object) -> None:
        pass

    def setLineWidth(self, *_: object) -> None:
        pass

    def setFont(self, *_: object) -> None:
        pass

    def rect(self, *_: object, **__: object) -> None:
        pass

    def roundRect(self, *_: object, **__: object) -> None:
        pass

    def line(self, *_: object) -> None:
        pass

    def drawImage(self, *_: object, **__: object) -> None:
        pass

    def drawString(self, _x: float, _y: float, text: str) -> None:
        self.text.append(text)

    def drawRightString(self, _x: float, _y: float, text: str) -> None:
        self.text.append(text)

    def drawCentredString(self, _x: float, _y: float, text: str) -> None:
        self.text.append(text)

    def stringWidth(self, text: str, _font_name: str, font_size: int) -> float:
        return len(text) * font_size * 0.55

    def showPage(self) -> None:
        self.page_breaks += 1

    def save(self) -> None:
        self.buffer.write(b"%PDF recording canvas")


def test_order_pdf_builder_returns_pdf_bytes() -> None:
    now = datetime.now(tz=timezone.utc)
    order = build_pdf_order(now=now)

    pdf_bytes = build_order_pdf(order=order, generated_at=now)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_order_pdf_builder_draws_ticket_state_and_receipt_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RecordingCanvas] = []

    class CapturingCanvas(RecordingCanvas):
        def __init__(self, buffer: BytesIO, *, pagesize: tuple[float, float]) -> None:
            super().__init__(buffer, pagesize=pagesize)
            captured.append(self)

    monkeypatch.setattr(order_pdf.canvas, "Canvas", CapturingCanvas)
    monkeypatch.setattr(order_pdf, "_build_qr_png", lambda value: BytesIO(value.encode()))
    monkeypatch.setattr(order_pdf, "ImageReader", lambda value: value)
    now = datetime.now(tz=timezone.utc)
    checked_in_at = now + timedelta(minutes=30)
    order = build_pdf_order(
        now=now,
        tickets=[
            build_pdf_ticket(
                "ticket-used",
                now=now,
                seat_row=2,
                seat_number=5,
                checked_in_at=checked_in_at,
                valid_for_entry=False,
            ),
            build_pdf_ticket(
                "ticket-cancelled",
                now=now,
                seat_row=2,
                seat_number=6,
                status="cancelled",
                valid_for_entry=False,
            ),
        ],
        valid_for_entry=False,
        entry_status_code="already_used",
        entry_status_message="All active tickets in this order were already checked in.",
    )

    pdf_bytes = build_order_pdf(order=order, generated_at=now)
    drawn_text = "\n".join(captured[0].text)

    assert pdf_bytes.startswith(b"%PDF")
    assert "Cinema Showcase" in drawn_text
    assert "Already used" in drawn_text
    assert "Row 2, seat 5" in drawn_text
    assert "Checked in:" in drawn_text
    assert "Row 2, seat 6" in drawn_text
    assert "Cancelled:" in drawn_text
    assert "Entry not valid" in drawn_text


def test_order_pdf_builder_continues_ticket_list_on_new_page(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RecordingCanvas] = []

    class CapturingCanvas(RecordingCanvas):
        def __init__(self, buffer: BytesIO, *, pagesize: tuple[float, float]) -> None:
            super().__init__(buffer, pagesize=pagesize)
            captured.append(self)

    monkeypatch.setattr(order_pdf.canvas, "Canvas", CapturingCanvas)
    monkeypatch.setattr(order_pdf, "_build_qr_png", lambda value: BytesIO(value.encode()))
    monkeypatch.setattr(order_pdf, "ImageReader", lambda value: value)
    now = datetime.now(tz=timezone.utc)
    tickets = [
        build_pdf_ticket(
            f"ticket-{index}",
            now=now,
            seat_row=(index // 12) + 1,
            seat_number=(index % 12) + 1,
        )
        for index in range(14)
    ]

    build_order_pdf(order=build_pdf_order(now=now, tickets=tickets), generated_at=now)

    assert captured[0].page_breaks >= 1
    assert "Tickets continued" in captured[0].text


@pytest.mark.parametrize(
    ("code", "label"),
    [
        ("valid", "Valid for entry"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        ("already_used", "Already used"),
        ("unknown", "Not valid for entry"),
    ],
)
def test_order_admission_label_maps_validation_states(code: str, label: str) -> None:
    assert order_pdf._order_admission_label(code) == label


def test_draw_wrapped_text_handles_empty_and_truncated_text() -> None:
    canvas = RecordingCanvas(BytesIO(), pagesize=order_pdf.A4)

    assert order_pdf._draw_wrapped_text(canvas, "", 10, 100, 40, "Helvetica", 10, 12) == 100
    end_y = order_pdf._draw_wrapped_text(
        canvas,
        "alpha beta gamma delta",
        10,
        100,
        12,
        "Helvetica",
        10,
        12,
        max_lines=1,
    )

    assert end_y == 88
    assert len(canvas.text) == 1


def test_register_font_uses_project_font_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeFontPath:
        @property
        def parents(self) -> "FakeFontPath":
            return self

        def __getitem__(self, index: int) -> "FakeFontPath":
            assert index == 3
            return self

        def __truediv__(self, _part: str) -> "FakeFontPath":
            return self

        def resolve(self) -> "FakeFontPath":
            return self

        def exists(self) -> bool:
            return True

        def __str__(self) -> str:
            return "NotoSans-Regular.ttf"

    registered_fonts: list[object] = []

    monkeypatch.setattr(order_pdf, "Path", lambda _value: FakeFontPath())
    monkeypatch.setattr(order_pdf.pdfmetrics, "getRegisteredFontNames", lambda: [])
    monkeypatch.setattr(order_pdf, "TTFont", lambda name, path: {"name": name, "path": path})
    monkeypatch.setattr(order_pdf.pdfmetrics, "registerFont", registered_fonts.append)

    assert order_pdf._register_font() == "NotoSansCinema"
    assert registered_fonts == [{"name": "NotoSansCinema", "path": "NotoSans-Regular.ttf"}]

    monkeypatch.setattr(order_pdf.pdfmetrics, "getRegisteredFontNames", lambda: ["NotoSansCinema"])
    registered_fonts.clear()

    assert order_pdf._register_font() == "NotoSansCinema"
    assert registered_fonts == []
