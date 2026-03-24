import type { SeatAvailability } from "@/types/domain";

interface SeatBadgeProps {
  seat: SeatAvailability;
  selected: boolean;
  disabled?: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatBadge({ seat, selected, disabled = false, onSelect }: SeatBadgeProps) {
  const stateClass = seat.is_available ? "seat--free" : "seat--taken";

  return (
    <button
      type="button"
      className={`seat ${stateClass}${selected ? " seat--selected" : ""}`}
      aria-pressed={selected}
      disabled={disabled || !seat.is_available}
      onClick={() => onSelect(seat)}
    >
      {seat.row}-{seat.number}
    </button>
  );
}
