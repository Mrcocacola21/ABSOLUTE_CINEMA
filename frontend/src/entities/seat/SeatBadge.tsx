import type { SeatAvailability } from "@/types/domain";

interface SeatBadgeProps {
  seat: SeatAvailability;
  selected: boolean;
  disabled?: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatBadge({ seat, selected, disabled = false, onSelect }: SeatBadgeProps) {
  const stateClass = seat.is_available ? "seat--free" : "seat--taken";
  const availabilityLabel = seat.is_available ? "available" : "occupied";

  return (
    <button
      type="button"
      className={`seat ${stateClass}${selected ? " seat--selected" : ""}`}
      aria-pressed={selected}
      aria-label={`Row ${seat.row}, seat ${seat.number}, ${selected ? "selected, " : ""}${availabilityLabel}`}
      disabled={disabled || !seat.is_available}
      onClick={() => onSelect(seat)}
      title={`Row ${seat.row}, Seat ${seat.number}`}
    >
      <span className="seat__number">{seat.number}</span>
    </button>
  );
}
