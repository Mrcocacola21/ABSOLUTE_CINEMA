import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import {
  getSessionDetailsRequest,
  getSessionSeatsRequest,
  purchaseTicketRequest,
} from "@/api/schedule";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { formatCurrency, formatDateTime, formatStateLabel, formatTime } from "@/shared/presentation";
import { toScheduleDayKey } from "@/shared/scheduleTimeline";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { SeatAvailability, SessionDetails, SessionSeats } from "@/types/domain";
import { SeatMap } from "@/widgets/session/SeatMap";
import { PurchaseTicketCard } from "@/widgets/tickets/PurchaseTicketCard";

function formatSessionRange(startTime: string, endTime: string): string {
  return `${formatTime(startTime)}-${formatTime(endTime)}`;
}

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
        <>
          {details ? (
            <section className="page-header page-header--movie-detail session-hero">
              <div className="session-hero__main">
                <div className="session-hero__copy">
                  <p className="page-eyebrow">{t("viewSession")}</p>
                  <h1 className="page-title session-hero__title">{details.movie.title}</h1>
                  <div className="session-hero__session-line">
                    <span className="badge session-hero__status-badge">{formatStateLabel(details.status)}</span>
                    <p className="session-hero__schedule-line">
                      {formatDateTime(details.start_time)} | {formatSessionRange(details.start_time, details.end_time)}
                    </p>
                  </div>

                  {details.movie.genres.length > 0 ? (
                    <div className="meta-row session-hero__taxonomy">
                      {details.movie.genres.map((genre) => (
                        <span key={`${details.movie.id}-${genre}`} className="badge">
                          {genre}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <p className="page-subtitle session-hero__description">{details.movie.description}</p>
                </div>
              </div>

              <div className="session-hero__aside">
                <div className="session-hero__aside-head">
                  <div className="session-hero__section-copy">
                    <p className="page-eyebrow">{t("dateTime")}</p>
                    <h2 className="section-title session-hero__aside-title">{formatDateTime(details.start_time)}</h2>
                    <p className="session-hero__aside-subtitle">
                      {t("startsAt")}: {formatTime(details.start_time)} | {t("endsAt")}: {formatTime(details.end_time)}
                    </p>
                  </div>
                  <button
                    className="button--ghost"
                    type="button"
                    disabled={isLoading || isRefreshing || isSubmitting}
                    onClick={() => void loadSessionData({ background: Boolean(details || seats) })}
                  >
                    {isRefreshing ? "Refreshing..." : "Refresh"}
                  </button>
                </div>

                <div className="session-hero__facts">
                  <div className="session-hero__fact">
                    <span>{t("price")}</span>
                    <strong>{formatCurrency(details.price)}</strong>
                  </div>
                  <div className="session-hero__fact">
                    <span>{t("availableSeats")}</span>
                    <strong>
                      {details.available_seats}/{details.total_seats}
                    </strong>
                  </div>
                  <div className="session-hero__fact">
                    <span>{t("duration")}</span>
                    <strong>{details.movie.duration_minutes} min</strong>
                  </div>
                  <div className="session-hero__fact">
                    <span>{details.movie.age_rating ? t("ageRating") : t("endsAt")}</span>
                    <strong>{details.movie.age_rating ?? formatTime(details.end_time)}</strong>
                  </div>
                </div>

                <div className="actions-row session-hero__actions">
                  <Link to={`/movies/${details.movie.id}`} className="button">
                    {t("viewMovieDetailsAction")}
                  </Link>
                  <Link
                    to={`/schedule?day=${toScheduleDayKey(details.start_time)}&movieId=${details.movie.id}&sessionId=${details.id}`}
                    className="button--ghost"
                  >
                    {t("viewInScheduleAction")}
                  </Link>
                </div>
              </div>
            </section>
          ) : null}

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
        </>
      ) : null}
    </>
  );
}
