import { useTranslation } from "react-i18next";

import { formatCurrency } from "@/shared/presentation";
import type { SeatAvailability } from "@/types/domain";

interface PurchaseTicketCardProps {
  canPurchase: boolean;
  selectedSeats: SeatAvailability[];
  price?: number;
  availableSeats?: number;
  isSubmitting: boolean;
  statusHint?: string;
  onPurchase: () => void;
}

export function PurchaseTicketCard({
  canPurchase,
  selectedSeats,
  price,
  availableSeats,
  isSubmitting,
  statusHint,
  onPurchase,
}: PurchaseTicketCardProps) {
  const { t } = useTranslation();
  const selectedSeatLabels = selectedSeats.map((seat) => `${seat.row}-${seat.number}`);
  const totalPrice =
    price !== undefined && selectedSeats.length > 0 ? price * selectedSeats.length : undefined;
  const purchaseLabel = isSubmitting
    ? `${t("common.actions.purchaseTicket")}...`
    : selectedSeats.length > 1
      ? t("common.actions.purchaseTickets")
      : selectedSeats.length === 1
        ? t("common.actions.purchaseTicket")
        : t("common.actions.selectSeatsFirst");

  return (
    <aside className="booking-module__summary" aria-live="polite">
      <div className="booking-module__summary-main">
        <div className="booking-module__summary-header">
          <h3>{t("booking.summary.title")}</h3>
          <p className="muted">
            {selectedSeats.length > 0
              ? t("booking.summary.selectionReady")
              : t("booking.summary.selectionPrompt")}
          </p>
        </div>

        <div className={`booking-module__selection-card${selectedSeats.length > 0 ? " is-active" : ""}`}>
          <span className="booking-module__selection-label">
            {selectedSeats.length > 0
              ? selectedSeats.length === 1
                ? t("common.labels.selectedSeat")
                : t("common.labels.selectedSeats")
              : t("common.labels.selection")}
          </span>
          <strong>{selectedSeats.length > 0 ? `${selectedSeats.length}` : "--"}</strong>
          <p>
            {selectedSeats.length > 0
              ? selectedSeats.length === 1
                ? t("booking.summary.reserveSingle", { seats: selectedSeatLabels.join(", ") })
                : t("booking.summary.reserveMultiple", { seats: selectedSeatLabels.join(", ") })
              : t("common.hints.chooseSeatPrompt")}
          </p>
        </div>
      </div>

      <div className="booking-module__metric-grid">
        {availableSeats !== undefined ? (
          <div className="booking-module__metric">
            <span>{t("common.labels.availableSeats")}</span>
            <strong>{availableSeats}</strong>
          </div>
        ) : null}
        {price !== undefined ? (
          <div className="booking-module__metric">
            <span>{selectedSeats.length > 0 ? t("common.labels.pricePerTicket") : t("common.labels.price")}</span>
            <strong>{formatCurrency(price)}</strong>
          </div>
        ) : null}
        {totalPrice !== undefined ? (
          <div className="booking-module__metric">
            <span>{t("common.labels.total")}</span>
            <strong>{formatCurrency(totalPrice)}</strong>
          </div>
        ) : null}
      </div>

      <div className="booking-module__summary-actions">
        {statusHint ? <p className="booking-module__status-hint">{statusHint}</p> : null}

        <button
          type="button"
          className="button booking-module__button"
          disabled={!canPurchase || selectedSeats.length === 0 || isSubmitting}
          onClick={onPurchase}
        >
          {purchaseLabel}
        </button>
      </div>
    </aside>
  );
}
