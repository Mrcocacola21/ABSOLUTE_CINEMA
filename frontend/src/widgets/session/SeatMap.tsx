import { useTranslation } from "react-i18next";

import { SeatBadge } from "@/entities/seat/SeatBadge";
import type { SeatAvailability } from "@/types/domain";

interface SeatMapProps {
  seats: SeatAvailability[];
  selectedSeat: SeatAvailability | null;
  isLoading?: boolean;
  isDisabled?: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatMap({
  seats,
  selectedSeat,
  isLoading = false,
  isDisabled = false,
  onSelect,
}: SeatMapProps) {
  const { t } = useTranslation();
  const groupedRows = [...seats]
    .sort((left, right) => {
      if (left.row === right.row) {
        return left.number - right.number;
      }
      return left.row - right.row;
    })
    .reduce<Array<{ row: number; seats: SeatAvailability[] }>>((rows, seat) => {
      const lastRow = rows[rows.length - 1];

      if (!lastRow || lastRow.row !== seat.row) {
        rows.push({ row: seat.row, seats: [seat] });
        return rows;
      }

      lastRow.seats.push(seat);
      return rows;
    }, []);

  return (
    <div className="seat-map">
      <div className="seat-map__topline">
        <div>
          <h3>{t("seatMap")}</h3>
          <p className="muted">
            {isLoading
              ? "Refreshing current seat availability."
              : "Select an available seat to continue."}
          </p>
        </div>
        <div className={`seat-map__selection${selectedSeat ? " is-active" : ""}`}>
          {selectedSeat ? (
            <>
              {t("selectedSeat")}: <strong>{selectedSeat.row}-{selectedSeat.number}</strong>
            </>
          ) : (
            "Choose any available seat."
          )}
        </div>
      </div>

      <div className="seat-map__legend" role="group" aria-label="Seat status legend">
        <span className="seat-map__legend-item">
          <span className="seat-map__legend-swatch seat-map__legend-swatch--free" aria-hidden="true" />
          Available
        </span>
        <span className="seat-map__legend-item">
          <span className="seat-map__legend-swatch seat-map__legend-swatch--selected" aria-hidden="true" />
          Selected
        </span>
        <span className="seat-map__legend-item">
          <span className="seat-map__legend-swatch seat-map__legend-swatch--taken" aria-hidden="true" />
          Occupied
        </span>
      </div>

      {seats.length === 0 ? (
        <div className="empty-state">Seat availability is currently unavailable.</div>
      ) : (
        <div className="seat-map__shell">
          <div className="seat-map__screen" aria-hidden="true">
            <span>Screen</span>
          </div>
          <div className="seat-map__viewport">
            <div className="seat-map__layout" role="group" aria-label="Cinema seating area">
              {groupedRows.map((rowGroup) => (
                <div
                  key={rowGroup.row}
                  className="seat-map__row"
                  role="group"
                  aria-label={`Row ${rowGroup.row}`}
                >
                  <span className="seat-map__row-label" aria-hidden="true">
                    Row {rowGroup.row}
                  </span>
                  <div className="seat-grid" role="presentation">
                    {rowGroup.seats.map((seat) => (
                      <SeatBadge
                        key={`${seat.row}-${seat.number}`}
                        seat={seat}
                        disabled={isDisabled}
                        selected={selectedSeat?.row === seat.row && selectedSeat?.number === seat.number}
                        onSelect={onSelect}
                      />
                    ))}
                  </div>
                  <span className="seat-map__row-label seat-map__row-label--mirror" aria-hidden="true">
                    Row {rowGroup.row}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
