import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getMovieRequest, getScheduleRequest } from "@/api/schedule";
import { extractApiErrorMessage } from "@/shared/apiErrors";
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

export function MovieDetailsPage() {
  const { t } = useTranslation();
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
      setErrorMessage(extractApiErrorMessage(error, t("movieDetailsUnavailable")));
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

  return (
    <>
      <section className="page-header">
        <div>
          <p className="page-eyebrow">{t("movieDetailsEyebrow")}</p>
          <h1 className="page-title">{movie?.title ?? t("movieDetails")}</h1>
          <p className="page-subtitle">
            {movie?.description ?? t("movieDetailsUnavailable")}
          </p>
        </div>
        <div className="actions-row">
          <Link to="/movies" className="button--ghost">
            {t("backToCatalog")}
          </Link>
          {sessions[0] ? (
            <Link to={`/schedule/${sessions[0].id}`} className="button">
              {t("viewSession")}
            </Link>
          ) : (
            <Link to="/schedule" className="button--ghost">
              {t("browseSchedule")}
            </Link>
          )}
        </div>
      </section>

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading movie details"
          message="Fetching the movie card and its available sessions."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title="Unable to load movie details"
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadMovieDetails()}>
              Try again
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage && movie ? (
        <section className="movie-detail-grid">
          <article className="panel movie-detail-card movie-detail-card--poster">
            <div className="movie-detail-poster media-tile" aria-hidden="true">
              {movie.poster_url ? (
                <img src={movie.poster_url} alt="" className="media-tile__image" />
              ) : (
                <span>{getMovieMonogram(movie.title)}</span>
              )}
            </div>
            <div className="stats-row">
              <span className="badge">{movie.is_active ? t("activeLabel") : t("inactiveLabel")}</span>
              {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
              <span className="badge">
                {t("duration")}: {movie.duration_minutes} min
              </span>
            </div>
            {movie.genres.length > 0 ? <p className="badge">{movie.genres.join(", ")}</p> : null}
            {sessionWindow ? (
              <div className="movie-card__schedule">
                <div className="schedule-range">
                  <div>
                        <span className="muted">{t("nextSession")}</span>
                        <strong>{formatDateTime(sessionWindow.first.start_time)}</strong>
                      </div>
                      <div>
                        <span className="muted">{t("lastUpcomingSession")}</span>
                        <strong>{formatDateTime(sessionWindow.last.start_time)}</strong>
                      </div>
                </div>
              </div>
            ) : null}
          </article>

          <article className="panel movie-detail-card">
            <div className="toolbar-panel__header">
              <div>
                <p className="page-eyebrow">{t("upcomingSessions")}</p>
                <h2 className="section-title">{t("daySessionsTitle")}</h2>
              </div>
              <p className="toolbar-panel__summary">
                {sessions.length} {t("sessionsCount")}
              </p>
            </div>

            {sessions.length > 0 ? (
              <div className="list movie-session-list">
                {sessions.map((session) => (
                  <article key={session.id} className="card timeline-card">
                    <div className="timeline-card__time">
                        <strong>
                          {formatTime(session.start_time)}
                        </strong>
                        <span>{formatTime(session.end_time)}</span>
                    </div>
                    <div className="timeline-card__body">
                      <div className="meta-row">
                        <span className="badge">
                          {session.available_seats}/{session.total_seats}
                        </span>
                        <span className="badge">{formatCurrency(session.price)}</span>
                      </div>
                      <h3>{formatDateTime(session.start_time)}</h3>
                      <p className="muted">{t("sessionCardHint")}</p>
                    </div>
                    <div className="timeline-card__actions">
                      <Link to={`/schedule/${session.id}`} className="button">
                        {t("viewSession")}
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <section className="empty-state empty-state--panel">
                <h2>{t("noUpcomingSessionsTitle")}</h2>
                <p>{t("noUpcomingSessionsText")}</p>
                <Link to="/schedule" className="button--ghost">
                  {t("browseSchedule")}
                </Link>
              </section>
            )}
          </article>
        </section>
      ) : null}
    </>
  );
}
