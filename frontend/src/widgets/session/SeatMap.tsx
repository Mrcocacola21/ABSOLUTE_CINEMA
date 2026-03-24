import { useTranslation } from "react-i18next";

import { SeatBadge } from "@/entities/seat/SeatBadge";
import type { SeatAvailability } from "@/types/domain";

interface SeatMapProps {
  seats: SeatAvailability[];
  selectedSeat: SeatAvailability | null;
  availableSeats?: number;
  totalSeats?: number;
  isLoading?: boolean;
  isDisabled?: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatMap({
  seats,
  selectedSeat,
  availableSeats,
  totalSeats,
  isLoading = false,
  isDisabled = false,
  onSelect,
}: SeatMapProps) {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <div className="admin-section__header">
        <div>
          <h3>{t("seatMap")}</h3>
          <p className="muted">
            {isLoading
              ? "Refreshing current seat availability."
              : "Select an available seat to continue."}
          </p>
        </div>
        {availableSeats !== undefined && totalSeats !== undefined ? (
          <span className="badge">
            {availableSeats}/{totalSeats} available
          </span>
        ) : null}
      </div>

      <div className="stats-row seat-map__legend">
        <span className="badge">Available</span>
        <span className="badge">Taken</span>
        {selectedSeat ? (
          <span className="badge">
            Selected: {selectedSeat.row}-{selectedSeat.number}
          </span>
        ) : null}
      </div>

      {seats.length === 0 ? (
        <div className="empty-state">Seat availability is currently unavailable.</div>
      ) : (
        <div className="seat-grid">
          {seats.map((seat) => (
            <SeatBadge
              key={`${seat.row}-${seat.number}`}
              seat={seat}
              disabled={isDisabled}
              selected={selectedSeat?.row === seat.row && selectedSeat?.number === seat.number}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </section>
  );
}
