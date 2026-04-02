import { useTranslation } from "react-i18next";

import { SeatBadge } from "@/entities/seat/SeatBadge";
import type { SeatAvailability } from "@/types/domain";

interface SeatMapProps {
  seats: SeatAvailability[];
  selectedSeats: SeatAvailability[];
  isLoading?: boolean;
  isDisabled?: boolean;
  onSelect: (seat: SeatAvailability) => void;
}

export function SeatMap({
  seats,
  selectedSeats,
  isLoading = false,
  isDisabled = false,
  onSelect,
}: SeatMapProps) {
  const { t } = useTranslation();
  const selectedSeatLabels = selectedSeats.map((seat) => `${seat.row}-${seat.number}`);
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
          <h3>{t("booking.seatMap.title")}</h3>
          <p className="muted">
            {isLoading
              ? t("booking.seatMap.refreshing")
              : t("booking.seatMap.chooseHint")}
          </p>
        </div>
        <div className={`seat-map__selection${selectedSeats.length > 0 ? " is-active" : ""}`}>
          {selectedSeats.length > 0 ? (
            <>
              {selectedSeats.length === 1 ? t("common.labels.selectedSeat") : t("common.labels.selectedSeats")}:{" "}
              <strong>{selectedSeatLabels.join(", ")}</strong>
            </>
          ) : (
            t("booking.seatMap.emptySelection")
          )}
        </div>
      </div>

      <div className="seat-map__legend" role="group" aria-label={t("booking.seatMap.legend.label")}>
        <span className="seat-map__legend-item">
          <span className="seat-map__legend-swatch seat-map__legend-swatch--free" aria-hidden="true" />
          {t("booking.seatMap.legend.available")}
        </span>
        <span className="seat-map__legend-item">
          <span className="seat-map__legend-swatch seat-map__legend-swatch--selected" aria-hidden="true" />
          {t("booking.seatMap.legend.selected")}
        </span>
        <span className="seat-map__legend-item">
          <span className="seat-map__legend-swatch seat-map__legend-swatch--taken" aria-hidden="true" />
          {t("booking.seatMap.legend.occupied")}
        </span>
      </div>

      {seats.length === 0 ? (
        <div className="empty-state">{t("booking.seatMap.unavailable")}</div>
      ) : (
        <div className="seat-map__shell">
          <div className="seat-map__screen" aria-hidden="true">
            <span>{t("booking.seatMap.screen")}</span>
          </div>
          <div className="seat-map__viewport">
            <div className="seat-map__layout" role="group" aria-label={t("booking.seatMap.seatingArea")}>
              {groupedRows.map((rowGroup) => (
                <div
                  key={rowGroup.row}
                  className="seat-map__row"
                  role="group"
                  aria-label={t("booking.seatMap.rowLabel", { row: rowGroup.row })}
                >
                  <span className="seat-map__row-label" aria-hidden="true">
                    {t("booking.seatMap.rowLabel", { row: rowGroup.row })}
                  </span>
                  <div className="seat-grid" role="presentation">
                    {rowGroup.seats.map((seat) => (
                      <SeatBadge
                        key={`${seat.row}-${seat.number}`}
                        seat={seat}
                        disabled={isDisabled}
                        selected={selectedSeats.some(
                          (selectedSeat) =>
                            selectedSeat.row === seat.row && selectedSeat.number === seat.number,
                        )}
                        onSelect={onSelect}
                      />
                    ))}
                  </div>
                  <span className="seat-map__row-label seat-map__row-label--mirror" aria-hidden="true">
                    {t("booking.seatMap.rowLabel", { row: rowGroup.row })}
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
