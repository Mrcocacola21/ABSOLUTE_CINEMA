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
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
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
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error" | "info";
    title: string;
    message: string;
  } | null>(null);

  async function loadSessionData(options?: { background?: boolean }) {
    const background = options?.background ?? false;
    if (background) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
      setErrorMessage("");
    }

    try {
      const [detailsResponse, seatsResponse] = await Promise.all([
        getSessionDetailsRequest(sessionId),
        getSessionSeatsRequest(sessionId),
      ]);
      setDetails(detailsResponse.data);
      setSeats(seatsResponse.data);
      setErrorMessage("");
      setSelectedSeat((currentSeat) => {
        if (!currentSeat) {
          return null;
        }
        const stillAvailable = seatsResponse.data.seats.some(
          (seat) =>
            seat.row === currentSeat.row &&
            seat.number === currentSeat.number &&
            seat.is_available,
        );
        return stillAvailable ? currentSeat : null;
      });
    } catch (error) {
      const message = extractApiErrorMessage(error, t("sessionDataUnavailable"));
      if (background) {
        setFeedback({
          tone: "error",
          title: "Unable to refresh session data",
          message,
        });
      } else {
        setDetails(null);
        setSeats(null);
        setSelectedSeat(null);
        setErrorMessage(message);
      }
    } finally {
      if (background) {
        setIsRefreshing(false);
      } else {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    setFeedback(null);
    void loadSessionData();
  }, [sessionId, t]);

  async function handlePurchase() {
    if (!selectedSeat) {
      return;
    }
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await purchaseTicketRequest(sessionId, selectedSeat.row, selectedSeat.number);
      await loadSessionData({ background: true });
      setFeedback({
        tone: "success",
        title: "Ticket purchased",
        message: `Seat ${selectedSeat.row}-${selectedSeat.number} is now reserved for you.`,
      });
      setSelectedSeat(null);
    } catch (error) {
      setFeedback({
        tone: "error",
        title: "Ticket purchase failed",
        message: extractApiErrorMessage(error, t("ticketPurchaseFailed")),
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  const isSessionPurchasable = Boolean(
    isAuthenticated &&
      details &&
      seats &&
      details.status === "scheduled" &&
      new Date(details.start_time).getTime() > Date.now() &&
      seats.available_seats > 0,
  );

  const purchaseHint = !isAuthenticated
    ? "Sign in to purchase a ticket for this session."
    : seats && seats.available_seats === 0
      ? "This session is sold out."
      : details && !isSessionPurchasable
        ? "This session is not available for purchase."
      : undefined;

  return (
    <>
      <section className="panel">
        <div className="toolbar-panel__header">
          <div>
            <h1 className="page-title">
              {details ? details.movie.title : t("viewSession")}
            </h1>
            <p className="muted">
              {details
                ? `${formatDateTime(details.start_time)} | ${t("price")}: ${formatCurrency(details.price)}`
                : t("sessionInfoLoading")}
            </p>
          </div>
          <div className="actions-row">
            <button
              className="button--ghost"
              type="button"
              disabled={isLoading || isRefreshing || isSubmitting}
              onClick={() => void loadSessionData({ background: Boolean(details || seats) })}
            >
              {isRefreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>
        <div className="stats-row">
          {details ? <span className="badge">{formatStateLabel(details.status)}</span> : null}
          {details?.movie.genres.length ? <span className="badge">{details.movie.genres.join(", ")}</span> : null}
          {details ? (
            <span className="badge">
              {details.available_seats}/{details.total_seats}
            </span>
          ) : null}
        </div>
      </section>

      {feedback ? (
        <StatusBanner
          tone={feedback.tone}
          title={feedback.title}
          message={feedback.message}
        />
      ) : null}

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading session details"
          message="Fetching session info, seat availability, and ticket options."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title="Unable to load this session"
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadSessionData()}>
              Try again
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage ? (
        <section className="panel booking-module">
          <div className="booking-module__header">
            <div className="booking-module__copy">
              <h2 className="section-title">
                {t("seatMap")} | {t("ticketPurchase")}
              </h2>
              <p className="muted">
                {selectedSeat
                  ? `Seat ${selectedSeat.row}-${selectedSeat.number} is selected. Review the summary and confirm the booking in the same flow.`
                  : "Choose a seat from the map, review the ticket summary, and complete the purchase without leaving this booking module."}
              </p>
            </div>
            <div className="booking-module__stats">
              {seats ? (
                <span className="badge">
                  {seats.available_seats}/{seats.total_seats} {t("availableSeats")}
                </span>
              ) : null}
              {details?.price !== undefined ? (
                <span className="badge">
                  {t("price")}: {formatCurrency(details.price)}
                </span>
              ) : null}
              {selectedSeat ? (
                <span className="badge">
                  {t("selectedSeat")}: {selectedSeat.row}-{selectedSeat.number}
                </span>
              ) : null}
            </div>
          </div>

          <div className="booking-module__body">
            <SeatMap
              seats={seats?.seats ?? []}
              selectedSeat={selectedSeat}
              isLoading={isRefreshing}
              isDisabled={!isSessionPurchasable || isSubmitting}
              onSelect={setSelectedSeat}
            />
            <PurchaseTicketCard
              canPurchase={isSessionPurchasable}
              selectedSeat={selectedSeat}
              price={details?.price}
              availableSeats={seats?.available_seats}
              isSubmitting={isSubmitting}
              statusHint={purchaseHint}
              onPurchase={() => void handlePurchase()}
            />
          </div>
        </section>
      ) : null}

      {!isLoading && !errorMessage && details ? (
        <section className="panel">
          <h3>{details.movie.title}</h3>
          <p className="muted">{details.movie.description}</p>
          <div className="stats-row">
            <span className="badge">{t("duration")}: {details.movie.duration_minutes}</span>
            {details.movie.age_rating ? <span className="badge">{details.movie.age_rating}</span> : null}
            <span className="badge">{formatStateLabel(details.status)}</span>
            <span className="badge">{details.available_seats}/{details.total_seats}</span>
          </div>
        </section>
      ) : null}
    </>
  );
}
