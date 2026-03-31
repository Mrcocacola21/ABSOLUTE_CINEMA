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
    ? "Purchasing..."
    : selectedSeats.length > 1
      ? "Purchase tickets"
      : selectedSeats.length === 1
        ? t("purchaseTicketAction")
        : "Select seats first";

  return (
    <aside className="booking-module__summary" aria-live="polite">
      <div className="booking-module__summary-main">
        <div className="booking-module__summary-header">
          <h3>{t("ticketPurchase")}</h3>
          <p className="muted">
            {selectedSeats.length > 0
              ? "Your selected seats are ready to reserve."
              : "Select seats from the map to unlock checkout."}
          </p>
        </div>

        <div className={`booking-module__selection-card${selectedSeats.length > 0 ? " is-active" : ""}`}>
          <span className="booking-module__selection-label">
            {selectedSeats.length > 0 ? (selectedSeats.length === 1 ? t("selectedSeat") : "Selected seats") : "Selection"}
          </span>
          <strong>{selectedSeats.length > 0 ? `${selectedSeats.length}` : "--"}</strong>
          <p>
            {selectedSeats.length > 0
              ? `Seats ${selectedSeatLabels.join(", ")} will be reserved when you confirm the purchase.`
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
            <span>{selectedSeats.length > 0 ? "Price per ticket" : t("price")}</span>
            <strong>{formatCurrency(price)}</strong>
          </div>
        ) : null}
        {totalPrice !== undefined ? (
          <div className="booking-module__metric">
            <span>Total</span>
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
