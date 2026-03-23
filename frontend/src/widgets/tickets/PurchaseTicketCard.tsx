import { useTranslation } from "react-i18next";

import type { SeatAvailability } from "@/types/domain";

interface PurchaseTicketCardProps {
  canPurchase: boolean;
  selectedSeat: SeatAvailability | null;
  price?: number;
  isSubmitting: boolean;
  statusHint?: string;
  onPurchase: () => void;
}

export function PurchaseTicketCard({
  canPurchase,
  selectedSeat,
  price,
  isSubmitting,
  statusHint,
  onPurchase,
}: PurchaseTicketCardProps) {
  const { t } = useTranslation();

  return (
    <aside className="form-card">
      <h3>{t("ticketPurchase")}</h3>
      <p className="muted">
        {selectedSeat
          ? `${t("selectedSeat")}: ${selectedSeat.row}-${selectedSeat.number}`
          : t("chooseSeatPrompt")}
      </p>
      {statusHint ? <p className="muted">{statusHint}</p> : null}
      {price !== undefined ? <p className="badge">{t("price")}: {price}</p> : null}
      <button
        type="button"
        className="button"
        disabled={!canPurchase || !selectedSeat || isSubmitting}
        onClick={onPurchase}
      >
        {isSubmitting ? t("processing") : t("purchaseTicketAction")}
      </button>
    </aside>
  );
}
