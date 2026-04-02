import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { purchaseOrderRequest } from "@/api/orders";
import {
  getSessionDetailsRequest,
  getSessionSeatsRequest,
} from "@/api/schedule";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getGenreLabel } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
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
  const { t, i18n } = useTranslation();
  const { sessionId = "" } = useParams();
  const { isAuthenticated } = useAuth();
  const [details, setDetails] = useState<SessionDetails | null>(null);
  const [seats, setSeats] = useState<SessionSeats | null>(null);
  const [selectedSeats, setSelectedSeats] = useState<SeatAvailability[]>([]);
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
      setSelectedSeats((currentSeats) => {
        if (currentSeats.length === 0) {
          return [];
        }
        return currentSeats.filter((currentSeat) =>
          seatsResponse.data.seats.some(
            (seat) =>
              seat.row === currentSeat.row &&
              seat.number === currentSeat.number &&
              seat.is_available,
          ),
        );
      });
    } catch (error) {
      const message = extractApiErrorMessage(error, t("session.errors.unavailable"));
      if (background) {
        setFeedback({
          tone: "error",
          title: t("session.errors.refreshTitle"),
          message,
        });
      } else {
        setDetails(null);
        setSeats(null);
        setSelectedSeats([]);
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

  function handleSeatToggle(seat: SeatAvailability) {
    setSelectedSeats((currentSeats) => {
      const isAlreadySelected = currentSeats.some(
        (selectedSeat) => selectedSeat.row === seat.row && selectedSeat.number === seat.number,
      );
      if (isAlreadySelected) {
        return currentSeats.filter(
          (selectedSeat) => !(selectedSeat.row === seat.row && selectedSeat.number === seat.number),
        );
      }
      return [...currentSeats, seat].sort((left, right) => {
        if (left.row === right.row) {
          return left.number - right.number;
        }
        return left.row - right.row;
      });
    });
  }

  async function handlePurchase() {
    if (selectedSeats.length === 0) {
      return;
    }
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await purchaseOrderRequest({
        session_id: sessionId,
        seats: selectedSeats.map((seat) => ({
          seat_row: seat.row,
          seat_number: seat.number,
        })),
      });
      await loadSessionData({ background: true });
      const selectedSeatLabels = selectedSeats.map((seat) => `${seat.row}-${seat.number}`).join(", ");
      setFeedback({
        tone: "success",
        title:
          selectedSeats.length > 1
            ? t("session.purchase.successMultipleTitle")
            : t("session.purchase.successSingleTitle"),
        message:
          selectedSeats.length > 1
            ? t("session.purchase.successMultipleMessage", { seats: selectedSeatLabels })
            : t("session.purchase.successSingleMessage", { seats: selectedSeatLabels }),
      });
      setSelectedSeats([]);
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("session.purchase.failedTitle"),
        message: extractApiErrorMessage(error, t("session.purchase.failedMessage")),
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
    ? t("session.purchase.signInRequired")
    : seats && seats.available_seats === 0
      ? t("session.purchase.soldOut")
      : details && !isSessionPurchasable
        ? t("session.purchase.unavailable")
        : undefined;

  const movieTitle = details ? getLocalizedText(details.movie.title, i18n.language) : "";
  const movieDescription = details ? getLocalizedText(details.movie.description, i18n.language) : "";

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
          title={t("session.loading.title")}
          message={t("session.loading.message")}
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title={t("session.errors.title")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadSessionData()}>
              {t("common.actions.retry")}
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
                  <p className="page-eyebrow">{t("session.detailsEyebrow")}</p>
                  <h1 className="page-title session-hero__title">{movieTitle}</h1>
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
                          {getGenreLabel(genre, i18n.language)}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <p className="page-subtitle session-hero__description">{movieDescription}</p>
                </div>
              </div>

              <div className="session-hero__aside">
                <div className="session-hero__aside-head">
                  <div className="session-hero__section-copy">
                    <p className="page-eyebrow">{t("common.labels.dateTime")}</p>
                    <h2 className="section-title session-hero__aside-title">{formatDateTime(details.start_time)}</h2>
                    <p className="session-hero__aside-subtitle">
                      {t("common.labels.startsAt")}: {formatTime(details.start_time)} | {t("common.labels.endsAt")}:{" "}
                      {formatTime(details.end_time)}
                    </p>
                  </div>
                  <button
                    className="button--ghost"
                    type="button"
                    disabled={isLoading || isRefreshing || isSubmitting}
                    onClick={() => void loadSessionData({ background: Boolean(details || seats) })}
                  >
                    {isRefreshing ? t("session.refresh.loading") : t("session.refresh.idle")}
                  </button>
                </div>

                <div className="session-hero__facts">
                  <div className="session-hero__fact">
                    <span>{t("common.labels.price")}</span>
                    <strong>{formatCurrency(details.price)}</strong>
                  </div>
                  <div className="session-hero__fact">
                    <span>{t("common.labels.availableSeats")}</span>
                    <strong>
                      {details.available_seats}/{details.total_seats}
                    </strong>
                  </div>
                  <div className="session-hero__fact">
                    <span>{t("common.labels.duration")}</span>
                    <strong>
                      {details.movie.duration_minutes} {t("common.units.minutesShort")}
                    </strong>
                  </div>
                  <div className="session-hero__fact">
                    <span>{details.movie.age_rating ? t("common.labels.ageRating") : t("common.labels.endsAt")}</span>
                    <strong>{details.movie.age_rating ?? formatTime(details.end_time)}</strong>
                  </div>
                </div>

                <div className="actions-row session-hero__actions">
                  <Link to={`/movies/${details.movie.id}`} className="button">
                    {t("common.actions.viewMovieDetails")}
                  </Link>
                  <Link
                    to={`/schedule?day=${toScheduleDayKey(details.start_time)}&movieId=${details.movie.id}&sessionId=${details.id}`}
                    className="button--ghost"
                  >
                    {t("common.actions.viewInSchedule")}
                  </Link>
                </div>
              </div>
            </section>
          ) : null}

          <section className="panel booking-module">
            <div className="booking-module__header">
              <div className="booking-module__copy">
                <h2 className="section-title">
                  {t("booking.module.title")}
                </h2>
                <p className="muted">
                  {selectedSeats.length > 0
                    ? t("booking.module.introSelected", {
                        count: selectedSeats.length,
                        seatLabel:
                          selectedSeats.length === 1
                            ? t("common.labels.selectedSeat").toLowerCase()
                            : t("common.labels.selectedSeats").toLowerCase(),
                      })
                    : t("booking.module.introEmpty")}
                </p>
              </div>
              <div className="booking-module__stats">
                {seats ? (
                  <span className="badge">
                    {seats.available_seats}/{seats.total_seats} {t("common.labels.availableSeats")}
                  </span>
                ) : null}
                {details?.price !== undefined ? (
                  <span className="badge">
                    {t("common.labels.price")}: {formatCurrency(details.price)}
                  </span>
                ) : null}
                {selectedSeats.length > 0 ? (
                  <span className="badge">
                    {selectedSeats.length === 1
                      ? t("common.labels.selectedSeat")
                      : t("common.labels.selectedSeats")}
                    :{" "}
                    {selectedSeats.map((seat) => `${seat.row}-${seat.number}`).join(", ")}
                  </span>
                ) : null}
                {selectedSeats.length > 1 && details?.price !== undefined ? (
                  <span className="badge">
                    {t("booking.module.totalLabel")}: {formatCurrency(details.price * selectedSeats.length)}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="booking-module__body">
              <SeatMap
                seats={seats?.seats ?? []}
                selectedSeats={selectedSeats}
                isLoading={isRefreshing}
                isDisabled={!isSessionPurchasable || isSubmitting}
                onSelect={handleSeatToggle}
              />
              <PurchaseTicketCard
                canPurchase={isSessionPurchasable}
                selectedSeats={selectedSeats}
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
