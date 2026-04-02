import i18n from "@/i18n";

import type { SeatAvailability } from "@/types/domain";

interface SeatBadgeProps {
  seat: SeatAvailability;
  selected: boolean;
  disabled?: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatBadge({ seat, selected, disabled = false, onSelect }: SeatBadgeProps) {
  const stateClass = seat.is_available ? "seat--free" : "seat--taken";
  const availabilityLabel = seat.is_available
    ? i18n.t("booking.seatMap.legend.available")
    : i18n.t("booking.seatMap.legend.occupied");
  const rowLabel = i18n.t("common.labels.row");
  const seatLabel = i18n.t("common.labels.seat");
  const selectedLabel = i18n.t("booking.seatMap.legend.selected");

  return (
    <button
      type="button"
      className={`seat ${stateClass}${selected ? " seat--selected" : ""}`}
      aria-pressed={selected}
      aria-label={`${rowLabel} ${seat.row}, ${seatLabel.toLowerCase()} ${seat.number}, ${
        selected ? `${selectedLabel.toLowerCase()}, ` : ""
      }${availabilityLabel.toLowerCase()}`}
      disabled={disabled || !seat.is_available}
      onClick={() => onSelect(seat)}
      title={`${rowLabel} ${seat.row}, ${seatLabel} ${seat.number}`}
    >
      <span className="seat__number">{seat.number}</span>
    </button>
  );
}
