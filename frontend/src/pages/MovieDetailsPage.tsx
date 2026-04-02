import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getMovieRequest, getScheduleRequest } from "@/api/schedule";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getGenreLabel } from "@/shared/genres";
import { getIntlLocale, getLocalizedText } from "@/shared/localization";
import { getMovieStatusTranslationKey } from "@/shared/movieStatus";
import { formatCurrency, formatDateTime, formatTime } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatSessionDayNumber(value: string, language: string): string {
  return new Date(value).toLocaleDateString(getIntlLocale(language), {
    day: "2-digit",
  });
}

function formatSessionMonth(value: string, language: string): string {
  return new Date(value).toLocaleDateString(getIntlLocale(language), {
    month: "short",
  });
}

function formatSessionDateLabel(value: string, language: string): string {
  return new Date(value).toLocaleDateString(getIntlLocale(language), {
    weekday: "short",
    day: "2-digit",
    month: "short",
  });
}

function formatSessionRange(startTime: string, endTime: string): string {
  return `${formatTime(startTime)}-${formatTime(endTime)}`;
}

export function MovieDetailsPage() {
  const { t, i18n } = useTranslation();
  const { movieId = "" } = useParams();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [sessions, setSessions] = useState<ScheduleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadMovieDetails() {
    setIsLoading(true);
    try {
      const [movieResponse, scheduleResponse] = await Promise.all([
        getMovieRequest(movieId, { includeInactive: true }),
        getScheduleRequest({
          sortBy: "start_time",
          sortOrder: "asc",
          movieId,
          limit: "100",
          offset: "0",
        }),
      ]);
      setMovie(movieResponse.data);
      setSessions(scheduleResponse.data);
      setErrorMessage("");
    } catch (error) {
      setMovie(null);
      setSessions([]);
      setErrorMessage(extractApiErrorMessage(error, t("movie.errors.unavailable")));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadMovieDetails();
  }, [movieId, t]);

  const sessionWindow = useMemo(() => {
    if (sessions.length === 0) {
      return null;
    }

    return {
      first: sessions[0],
      last: sessions[sessions.length - 1],
    };
  }, [sessions]);

  const statusLabel = movie ? t(getMovieStatusTranslationKey(movie.status)) : "--";
  const movieTitle = movie ? getLocalizedText(movie.title, i18n.language) : "";
  const movieDescription = movie ? getLocalizedText(movie.description, i18n.language) : "";

  return (
    <>
      <section className="page-header page-header--movie-detail movie-hero">
        <div className="movie-hero__copy">
          <p className="page-eyebrow">{t("movie.details.eyebrow")}</p>
          <h1 className="page-title">{movie ? movieTitle : t("movie.details.title")}</h1>

          {movie && movie.genres.length > 0 ? (
            <div className="meta-row movie-hero__taxonomy">
              {movie.genres.map((genre) => (
                <span key={`${movie.id}-${genre}`} className="badge">
                  {getGenreLabel(genre, i18n.language)}
                </span>
              ))}
            </div>
          ) : null}

          <p className="page-subtitle movie-hero__description">
            {movie ? movieDescription : t("movie.errors.unavailable")}
          </p>
        </div>

        <div className="movie-hero__aside">
          <div className="movie-hero__facts">
            <div className="movie-hero__fact">
              <span>{t("common.labels.status")}</span>
              <strong>{statusLabel}</strong>
            </div>
            <div className="movie-hero__fact">
              <span>{t("common.labels.duration")}</span>
              <strong>{movie ? `${movie.duration_minutes} ${t("common.units.minutesShort")}` : "--"}</strong>
            </div>
            <div className="movie-hero__fact">
              <span>{movie?.age_rating ? t("common.labels.ageRating") : t("common.labels.sessions")}</span>
              <strong>{movie?.age_rating ?? sessions.length}</strong>
            </div>
          </div>

          {sessionWindow ? (
            <div className="movie-hero__session-preview">
              <span className="movie-hero__session-label">{t("movie.sessionWindow.nextSession")}</span>
              <strong>{formatSessionDateLabel(sessionWindow.first.start_time, i18n.language)}</strong>
              <span>{formatSessionRange(sessionWindow.first.start_time, sessionWindow.first.end_time)}</span>
            </div>
          ) : (
            <div className="movie-hero__session-preview movie-hero__session-preview--empty">
              <p className="muted">{t("movie.noUpcomingSessions.short")}</p>
            </div>
          )}

          <div className="actions-row movie-hero__actions">
            {sessions[0] ? (
              <Link to={`/schedule/${sessions[0].id}`} className="button">
                {t("common.actions.viewNextSession")}
              </Link>
            ) : (
              <Link to="/schedule" className="button--ghost">
                {t("common.actions.browseSchedule")}
              </Link>
            )}
            <Link to="/movies" className="button--ghost">
              {t("common.actions.backToCatalog")}
            </Link>
          </div>
        </div>
      </section>

      {isLoading ? (
        <StatePanel
          tone="loading"
          title={t("movie.loading.title")}
          message={t("movie.loading.message")}
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title={t("movie.errors.title")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadMovieDetails()}>
              {t("common.actions.retry")}
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage && movie ? (
        <section className="movie-detail-grid">
          <article className="panel movie-detail-card movie-detail-card--poster">
            <div className="movie-detail-card__poster-shell">
              <div className="movie-detail-poster media-tile" aria-hidden="true">
                {movie.poster_url ? (
                  <img src={movie.poster_url} alt="" className="media-tile__image" />
                ) : (
                  <span>{getMovieMonogram(movieTitle)}</span>
                )}
              </div>
            </div>

            <div className="movie-detail-card__copy">
              <div className="movie-detail-card__section-head movie-detail-card__section-head--stack">
                <div className="movie-detail-card__section-copy">
                  <p className="page-eyebrow">{t("common.labels.movie")}</p>
                  <h2 className="section-title">{t("movie.details.title")}</h2>
                </div>
              </div>

              <div className="movie-detail-card__fact-grid">
                <div className="movie-detail-card__fact">
                  <span>{t("common.labels.status")}</span>
                  <strong>{t(getMovieStatusTranslationKey(movie.status))}</strong>
                </div>
                <div className="movie-detail-card__fact">
                  <span>{t("common.labels.duration")}</span>
                  <strong>
                    {movie.duration_minutes} {t("common.units.minutesShort")}
                  </strong>
                </div>
                {movie.age_rating ? (
                  <div className="movie-detail-card__fact">
                    <span>{t("common.labels.ageRating")}</span>
                    <strong>{movie.age_rating}</strong>
                  </div>
                ) : null}
                <div className="movie-detail-card__fact">
                  <span>{t("common.labels.sessions")}</span>
                  <strong>{sessions.length}</strong>
                </div>
              </div>

              {movie.genres.length > 0 ? (
                <div className="meta-row movie-detail-card__genres">
                  {movie.genres.map((genre) => (
                    <span key={`${movie.id}-detail-${genre}`} className="badge">
                      {getGenreLabel(genre, i18n.language)}
                    </span>
                  ))}
                </div>
              ) : null}

              {sessionWindow ? (
                <div className="movie-detail-card__window">
                  <div className="movie-detail-card__window-row">
                    <span className="muted">{t("movie.sessionWindow.nextSession")}</span>
                    <strong>{formatSessionDateLabel(sessionWindow.first.start_time, i18n.language)}</strong>
                    <span>{formatSessionRange(sessionWindow.first.start_time, sessionWindow.first.end_time)}</span>
                  </div>
                  <div className="movie-detail-card__window-row">
                    <span className="muted">{t("movie.sessionWindow.lastUpcomingSession")}</span>
                    <strong>{formatSessionDateLabel(sessionWindow.last.start_time, i18n.language)}</strong>
                    <span>{formatSessionRange(sessionWindow.last.start_time, sessionWindow.last.end_time)}</span>
                  </div>
                </div>
              ) : null}
            </div>
          </article>

          <article className="panel movie-detail-card movie-detail-card--sessions">
            <div className="movie-detail-card__section-head">
              <div className="movie-detail-card__section-copy">
                <p className="page-eyebrow">{t("common.labels.upcomingSessions")}</p>
                <h2 className="section-title">{t("schedule.board.title")}</h2>
                <p className="muted">{t("common.hints.sessionCard")}</p>
              </div>
              <div className="movie-detail-card__section-summary">
                <span className="badge">
                  {sessions.length} {t("common.labels.sessions")}
                </span>
                {sessionWindow ? (
                  <span className="badge">{formatSessionDateLabel(sessionWindow.first.start_time, i18n.language)}</span>
                ) : null}
              </div>
            </div>

            {sessions.length > 0 ? (
              <div className="list movie-session-list">
                {sessions.map((session) => (
                  <article key={session.id} className="card timeline-card timeline-card--movie-detail">
                    <div className="timeline-card__date">
                      <strong>{formatSessionDayNumber(session.start_time, i18n.language)}</strong>
                      <span>{formatSessionMonth(session.start_time, i18n.language)}</span>
                    </div>

                    <div className="timeline-card__body">
                      <div className="timeline-card__headline">
                        <h3>{formatSessionRange(session.start_time, session.end_time)}</h3>
                        <p className="timeline-card__date-label">
                          {formatDateTime(session.start_time)}
                        </p>
                      </div>

                      <div className="meta-row timeline-card__meta">
                        <span className="badge">{formatCurrency(session.price)}</span>
                        <span className="badge">
                          {session.available_seats}/{session.total_seats}
                        </span>
                      </div>

                      <p className="muted">{t("common.hints.sessionCard")}</p>
                    </div>

                    <div className="timeline-card__actions">
                      <Link to={`/schedule/${session.id}`} className="button">
                        {t("common.actions.viewSession")}
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <section className="empty-state empty-state--panel">
                <h2>{t("movie.noUpcomingSessions.title")}</h2>
                <p>{t("movie.noUpcomingSessions.text")}</p>
                <Link to="/schedule" className="button--ghost">
                  {t("common.actions.browseSchedule")}
                </Link>
              </section>
            )}
          </article>
        </section>
      ) : null}
    </>
  );
}
