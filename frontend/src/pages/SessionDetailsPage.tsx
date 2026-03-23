import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import {
  getSessionDetailsRequest,
  getSessionSeatsRequest,
  purchaseTicketRequest,
} from "@/api/schedule";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import type { SeatAvailability, SessionDetails, SessionSeats } from "@/types/domain";
import { SeatMap } from "@/widgets/session/SeatMap";
import { PurchaseTicketCard } from "@/widgets/tickets/PurchaseTicketCard";

export function SessionDetailsPage() {
  const { t } = useTranslation();
  const { sessionId = "" } = useParams();
  const { isAuthenticated } = useAuth();
  const [details, setDetails] = useState<SessionDetails | null>(null);
  const [seats, setSeats] = useState<SessionSeats | null>(null);
  const [selectedSeat, setSelectedSeat] = useState<SeatAvailability | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    void Promise.all([
      getSessionDetailsRequest(sessionId),
      getSessionSeatsRequest(sessionId),
    ])
      .then(([detailsResponse, seatsResponse]) => {
        setDetails(detailsResponse.data);
        setSeats(seatsResponse.data);
      })
      .catch(() => {
        setStatusMessage(t("sessionDataUnavailable"));
      });
  }, [sessionId, t]);

  async function handlePurchase() {
    if (!selectedSeat) {
      return;
    }
    setIsSubmitting(true);
    try {
      await purchaseTicketRequest(sessionId, selectedSeat.row, selectedSeat.number);
      const [detailsResponse, seatsResponse] = await Promise.all([
        getSessionDetailsRequest(sessionId),
        getSessionSeatsRequest(sessionId),
      ]);
      setDetails(detailsResponse.data);
      setSeats(seatsResponse.data);
      setStatusMessage(t("ticketPurchaseSubmitted"));
      setSelectedSeat(null);
    } catch (error) {
      setStatusMessage(extractApiErrorMessage(error, t("ticketPurchaseFailed")));
    } finally {
      setIsSubmitting(false);
    }
  }

  const isSessionPurchasable = Boolean(
    isAuthenticated &&
      details &&
      details.status === "scheduled" &&
      new Date(details.start_time).getTime() > Date.now(),
  );

  const purchaseHint = !isAuthenticated
    ? "Sign in to buy tickets."
    : details && !isSessionPurchasable
      ? "This session is not available for ticket purchase."
      : undefined;

  return (
    <>
      <section className="panel">
        <h1 className="page-title">
          {details ? details.movie.title : t("viewSession")}
        </h1>
        <p className="muted">
          {details
            ? `${new Date(details.start_time).toLocaleString()} | ${t("price")}: ${details.price}`
            : t("sessionInfoLoading")}
        </p>
        {details?.movie.genres.length ? <p className="badge">{details.movie.genres.join(", ")}</p> : null}
        {statusMessage ? <p className="badge">{statusMessage}</p> : null}
      </section>
      <section className="split-grid">
        <SeatMap
          seats={seats?.seats ?? []}
          selectedSeat={selectedSeat}
          onSelect={setSelectedSeat}
        />
        <PurchaseTicketCard
          canPurchase={isSessionPurchasable}
          selectedSeat={selectedSeat}
          price={details?.price}
          isSubmitting={isSubmitting}
          statusHint={purchaseHint}
          onPurchase={() => void handlePurchase()}
        />
      </section>
      {details ? (
        <section className="panel">
          <h3>{details.movie.title}</h3>
          <p className="muted">{details.movie.description}</p>
          <div className="stats-row">
            <span className="badge">{t("duration")}: {details.movie.duration_minutes}</span>
            {details.movie.age_rating ? <span className="badge">{details.movie.age_rating}</span> : null}
            <span className="badge">{details.available_seats}/{details.total_seats}</span>
          </div>
        </section>
      ) : null}
    </>
  );
}
