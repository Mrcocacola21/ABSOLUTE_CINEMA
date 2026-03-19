import { useTranslation } from "react-i18next";

import { SeatBadge } from "@/entities/seat/SeatBadge";
import type { SeatAvailability } from "@/types/domain";

interface SeatMapProps {
  seats: SeatAvailability[];
  selectedSeat: SeatAvailability | null;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatMap({ seats, selectedSeat, onSelect }: SeatMapProps) {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <h3>{t("seatMap")}</h3>
      <div className="seat-grid">
        {seats.map((seat) => (
          <SeatBadge
            key={`${seat.row}-${seat.number}`}
            seat={seat}
            selected={selectedSeat?.row === seat.row && selectedSeat?.number === seat.number}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
