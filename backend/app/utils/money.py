"""Money helpers for payment-domain minor-unit accounting."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.core.exceptions import ValidationException


def amount_to_minor_units(amount: float | int | str | Decimal, *, exponent: int = 2) -> int:
    """Convert a major-unit amount into integer minor units."""
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationException("Amount must be numeric.") from exc

    if decimal_amount <= 0:
        raise ValidationException("Amount must be greater than zero.")

    multiplier = Decimal(10) ** exponent
    minor_units = (decimal_amount * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor_units)
