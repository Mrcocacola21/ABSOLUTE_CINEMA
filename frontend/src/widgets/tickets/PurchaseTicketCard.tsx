import { useTranslation } from "react-i18next";

import { formatCurrency } from "@/shared/presentation";
import type { SeatAvailability } from "@/types/domain";

interface PurchaseTicketCardProps {
  canPurchase: boolean;
  selectedSeat: SeatAvailability | null;
  price?: number;
  availableSeats?: number;
  isSubmitting: boolean;
  statusHint?: string;
  onPurchase: () => void;
}

export function PurchaseTicketCard({
  canPurchase,
  selectedSeat,
  price,
  availableSeats,
  isSubmitting,
  statusHint,
  onPurchase,
}: PurchaseTicketCardProps) {
  const { t } = useTranslation();
  const purchaseLabel = isSubmitting
    ? "Purchasing..."
    : selectedSeat
      ? t("purchaseTicketAction")
      : "Select a seat first";

  return (
    <aside className="booking-module__summary" aria-live="polite">
      <div className="booking-module__summary-main">
        <div className="booking-module__summary-header">
          <h3>{t("ticketPurchase")}</h3>
          <p className="muted">
            {selectedSeat
              ? "Your seat is ready to reserve."
              : "Select a seat from the map to unlock checkout."}
          </p>
        </div>

        <div className={`booking-module__selection-card${selectedSeat ? " is-active" : ""}`}>
          <span className="booking-module__selection-label">
            {selectedSeat ? t("selectedSeat") : "Selection"}
          </span>
          <strong>{selectedSeat ? `${selectedSeat.row}-${selectedSeat.number}` : "--"}</strong>
          <p>
            {selectedSeat
              ? "This exact seat will be reserved when you confirm the purchase."
              : t("chooseSeatPrompt")}
          </p>
        </div>
      </div>

      <div className="booking-module__metric-grid">
        {availableSeats !== undefined ? (
          <div className="booking-module__metric">
            <span>{t("availableSeats")}</span>
            <strong>{availableSeats}</strong>
          </div>
        ) : null}
        {price !== undefined ? (
          <div className="booking-module__metric">
            <span>{t("price")}</span>
            <strong>{formatCurrency(price)}</strong>
          </div>
        ) : null}
      </div>

      <div className="booking-module__summary-actions">
        {statusHint ? <p className="booking-module__status-hint">{statusHint}</p> : null}

        <button
          type="button"
          className="button booking-module__button"
          disabled={!canPurchase || !selectedSeat || isSubmitting}
          onClick={onPurchase}
        >
          {purchaseLabel}
        </button>
      </div>
    </aside>
  );
}
