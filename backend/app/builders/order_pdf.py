"""PDF generation for customer order receipts."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.schemas.order import OrderDetailsRead, OrderTicketRead

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 44
ACCENT = colors.HexColor("#C87035")
INK = colors.HexColor("#222222")
MUTED = colors.HexColor("#666666")
LIGHT = colors.HexColor("#F4EEE8")
BORDER = colors.HexColor("#DED7D0")
SUCCESS = colors.HexColor("#2E7D54")
DANGER = colors.HexColor("#A33B35")
WARNING = colors.HexColor("#9B6A20")


def build_order_pdf(*, order: OrderDetailsRead, generated_at: datetime) -> bytes:
    """Build a readable PDF receipt with a real validation QR code."""
    buffer = BytesIO()
    document = canvas.Canvas(buffer, pagesize=A4)
    font_name = _register_font()
    bold_font = font_name

    y = PAGE_HEIGHT - MARGIN
    movie_title = order.movie_title.resolve("en")

    document.setFillColor(ACCENT)
    document.rect(0, PAGE_HEIGHT - 86, PAGE_WIDTH, 86, fill=1, stroke=0)
    document.setFillColor(colors.white)
    document.setFont(bold_font, 22)
    document.drawString(MARGIN, PAGE_HEIGHT - 48, "Cinema Showcase")
    document.setFont(font_name, 11)
    document.drawString(MARGIN, PAGE_HEIGHT - 68, "Order receipt and entry validation")

    y -= 112
    document.setFillColor(INK)
    document.setFont(bold_font, 20)
    y = _draw_wrapped_text(document, movie_title, MARGIN, y, 330, bold_font, 20, 24)
    document.setFont(font_name, 10)
    document.setFillColor(MUTED)
    document.drawString(MARGIN, y - 8, f"Order #{order.id}")

    qr_buffer = _build_qr_png(order.validation_url)
    document.drawImage(
        ImageReader(qr_buffer),
        PAGE_WIDTH - MARGIN - 122,
        PAGE_HEIGHT - 226,
        width=122,
        height=122,
        preserveAspectRatio=True,
        mask="auto",
    )
    document.setFillColor(MUTED)
    document.setFont(font_name, 8)
    document.drawCentredString(PAGE_WIDTH - MARGIN - 61, PAGE_HEIGHT - 238, "Scan to validate")

    y -= 44
    y = _draw_status_band(document, order=order, y=y, font_name=font_name, bold_font=bold_font)

    y -= 18
    y = _draw_section_title(document, "Session", y, bold_font)
    session_rows = [
        ("Movie", movie_title),
        ("Session time", f"{_format_datetime(order.session_start_time)} - {_format_time(order.session_end_time)}"),
        ("Session status", _humanize(order.session_status)),
        ("Price per ticket", f"{order.session_price:.0f} UAH"),
        ("Hall", "Hall 1"),
    ]
    y = _draw_fact_grid(document, session_rows, y, font_name, bold_font)

    y -= 14
    y = _draw_section_title(document, "Order", y, bold_font)
    order_rows = [
        ("Order status", _humanize(order.status)),
        ("Created", _format_datetime(order.created_at)),
        ("Tickets", f"{order.tickets_count} total / {order.unchecked_active_tickets_count} not used"),
        ("Cancelled", str(order.cancelled_tickets_count)),
        ("Checked in", str(order.checked_in_tickets_count)),
        ("Total", f"{order.total_price:.0f} UAH"),
        ("Generated", _format_datetime(generated_at)),
    ]
    y = _draw_fact_grid(document, order_rows, y, font_name, bold_font)

    y -= 14
    y = _draw_section_title(document, "Tickets", y, bold_font)
    for ticket in order.tickets:
        if y < 110:
            document.showPage()
            y = PAGE_HEIGHT - MARGIN
            y = _draw_section_title(document, "Tickets continued", y, bold_font)
        y = _draw_ticket(document, ticket=ticket, y=y, font_name=font_name, bold_font=bold_font)

    y -= 6
    if y < 92:
        document.showPage()
        y = PAGE_HEIGHT - MARGIN

    document.setStrokeColor(BORDER)
    document.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    document.setFont(font_name, 9)
    document.setFillColor(MUTED)
    footer_text = (
        "Validation is checked against the live order state. "
        "Cancelled, expired, and already checked-in tickets are not valid for another entry."
    )
    _draw_wrapped_text(document, footer_text, MARGIN, y - 18, PAGE_WIDTH - (MARGIN * 2), font_name, 9, 12)

    document.save()
    buffer.seek(0)
    return buffer.getvalue()


def _register_font() -> str:
    font_path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "fonts" / "NotoSans-Regular.ttf"
    if font_path.exists() and "NotoSansCinema" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("NotoSansCinema", str(font_path)))
        return "NotoSansCinema"
    if font_path.exists():
        return "NotoSansCinema"
    return "Helvetica"


def _build_qr_png(value: str) -> BytesIO:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _draw_status_band(
    document: canvas.Canvas,
    *,
    order: OrderDetailsRead,
    y: float,
    font_name: str,
    bold_font: str,
) -> float:
    band_height = 54
    status_color = SUCCESS if order.valid_for_entry else (WARNING if order.entry_status_code == "already_used" else DANGER)
    document.setFillColor(LIGHT)
    document.roundRect(MARGIN, y - band_height, PAGE_WIDTH - (MARGIN * 2), band_height, 8, fill=1, stroke=0)
    document.setStrokeColor(status_color)
    document.setLineWidth(1.2)
    document.roundRect(MARGIN, y - band_height, PAGE_WIDTH - (MARGIN * 2), band_height, 8, fill=0, stroke=1)
    document.setFillColor(status_color)
    document.setFont(bold_font, 13)
    document.drawString(MARGIN + 16, y - 21, _order_admission_label(order.entry_status_code))
    document.setFillColor(INK)
    document.setFont(font_name, 9)
    _draw_wrapped_text(
        document,
        order.entry_status_message,
        MARGIN + 16,
        y - 37,
        PAGE_WIDTH - (MARGIN * 2) - 32,
        font_name,
        9,
        11,
    )
    return y - band_height


def _draw_section_title(document: canvas.Canvas, title: str, y: float, bold_font: str) -> float:
    document.setFillColor(INK)
    document.setFont(bold_font, 14)
    document.drawString(MARGIN, y, title)
    document.setStrokeColor(ACCENT)
    document.setLineWidth(1)
    document.line(MARGIN, y - 7, PAGE_WIDTH - MARGIN, y - 7)
    return y - 24


def _draw_fact_grid(
    document: canvas.Canvas,
    rows: list[tuple[str, str]],
    y: float,
    font_name: str,
    bold_font: str,
) -> float:
    column_width = (PAGE_WIDTH - (MARGIN * 2) - 14) / 2
    row_height = 38
    for index, (label, value) in enumerate(rows):
        column = index % 2
        if column == 0 and index > 0:
            y -= row_height + 8
        x = MARGIN + column * (column_width + 14)
        document.setFillColor(colors.white)
        document.setStrokeColor(BORDER)
        document.roundRect(x, y - row_height, column_width, row_height, 6, fill=1, stroke=1)
        document.setFillColor(MUTED)
        document.setFont(font_name, 7)
        document.drawString(x + 10, y - 14, label.upper())
        document.setFillColor(INK)
        document.setFont(bold_font, 9)
        _draw_wrapped_text(document, value, x + 10, y - 27, column_width - 20, bold_font, 9, 10, max_lines=1)
    return y - row_height


def _draw_ticket(
    document: canvas.Canvas,
    *,
    ticket: OrderTicketRead,
    y: float,
    font_name: str,
    bold_font: str,
) -> float:
    height = 58
    color = SUCCESS if ticket.valid_for_entry else (
        WARNING if ticket.checked_in_at is not None else (DANGER if ticket.status == "cancelled" else WARNING)
    )
    document.setFillColor(colors.white)
    document.setStrokeColor(BORDER)
    document.roundRect(MARGIN, y - height, PAGE_WIDTH - (MARGIN * 2), height, 8, fill=1, stroke=1)
    document.setFillColor(color)
    document.roundRect(MARGIN, y - height, 10, height, 8, fill=1, stroke=0)

    document.setFillColor(INK)
    document.setFont(bold_font, 12)
    document.drawString(MARGIN + 20, y - 20, f"Row {ticket.seat_row}, seat {ticket.seat_number}")
    document.setFillColor(MUTED)
    document.setFont(font_name, 8)
    document.drawString(MARGIN + 20, y - 36, f"Purchased: {_format_datetime(ticket.purchased_at)}")
    if ticket.cancelled_at:
        document.drawString(MARGIN + 20, y - 49, f"Cancelled: {_format_datetime(ticket.cancelled_at)}")
    if ticket.checked_in_at:
        document.drawString(MARGIN + 20, y - 49, f"Checked in: {_format_datetime(ticket.checked_in_at)}")

    document.setFillColor(color)
    document.setFont(bold_font, 9)
    document.drawRightString(PAGE_WIDTH - MARGIN - 18, y - 22, _humanize(ticket.status))
    document.setFillColor(INK)
    document.setFont(font_name, 8)
    document.drawRightString(
        PAGE_WIDTH - MARGIN - 18,
        y - 38,
        "Entry valid" if ticket.valid_for_entry else ("Already used" if ticket.checked_in_at else "Entry not valid"),
    )
    return y - height - 10


def _draw_wrapped_text(
    document: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    font_name: str,
    font_size: int,
    leading: int,
    *,
    max_lines: int | None = None,
) -> float:
    words = text.split()
    if not words:
        return y

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if document.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)

    if max_lines is not None:
        lines = lines[:max_lines]

    document.setFont(font_name, font_size)
    for line in lines:
        document.drawString(x, y, line)
        y -= leading
    return y


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%H:%M UTC")


def _humanize(value: str) -> str:
    return value.replace("_", " ").title()


def _order_admission_label(value: str) -> str:
    if value == "valid":
        return "Valid for entry"
    if value == "cancelled":
        return "Cancelled"
    if value == "expired":
        return "Expired"
    if value == "already_used":
        return "Already used"
    return "Not valid for entry"
