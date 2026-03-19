import type { SeatAvailability } from "@/types/domain";

interface SeatBadgeProps {
  seat: SeatAvailability;
  selected: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatBadge({ seat, selected, onSelect }: SeatBadgeProps) {
  const stateClass = seat.is_available ? "seat--free" : "seat--taken";

  return (
    <button
      type="button"
      className={`seat ${stateClass}`}
      aria-pressed={selected}
      disabled={!seat.is_available}
      onClick={() => onSelect(seat)}
      style={selected ? { outline: "2px solid #ffb570" } : undefined}
    >
      {seat.row}-{seat.number}
    </button>
  );
}
