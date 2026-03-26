import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { formatDateTime } from "@/shared/presentation";
import type { Movie, ScheduleItem } from "@/types/domain";

interface MovieCatalogCardProps {
  movie: Movie;
  sessionsCount: number;
  nextSession?: ScheduleItem;
  lastSession?: ScheduleItem;
}

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function MovieCatalogCard({
  movie,
  sessionsCount,
  nextSession,
  lastSession,
}: MovieCatalogCardProps) {
  const { t } = useTranslation();
  const statusClassName = movie.is_active
    ? "catalog-movie-card__status catalog-movie-card__status--active"
    : "catalog-movie-card__status catalog-movie-card__status--inactive";

  return (
    <article className="card catalog-movie-card">
      <div className="catalog-movie-card__hero">
        <Link to={`/movies/${movie.id}`} className="media-tile catalog-movie-card__media" aria-hidden="true">
          {movie.poster_url ? (
            <img src={movie.poster_url} alt="" className="media-tile__image" />
          ) : (
            <span>{getMovieMonogram(movie.title)}</span>
          )}
        </Link>

        <div className="catalog-movie-card__body">
          <div className="catalog-movie-card__topline">
            <div className="catalog-movie-card__title-row">
              <h3 className="catalog-movie-card__title">{movie.title}</h3>
              <span className={statusClassName}>{movie.is_active ? t("activeLabel") : t("inactiveLabel")}</span>
            </div>

            {movie.genres.length > 0 || movie.age_rating ? (
              <div className="meta-row catalog-movie-card__taxonomy">
                {movie.genres.map((genre) => (
                  <span key={`${movie.id}-${genre}`} className="badge">
                    {genre}
                  </span>
                ))}
                {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
              </div>
            ) : null}
          </div>

          {movie.description ? (
            <p className="muted catalog-movie-card__description">{movie.description}</p>
          ) : null}
        </div>
      </div>

      <div className="catalog-movie-card__facts">
        <div className="catalog-movie-card__fact">
          <span>{t("duration")}</span>
          <strong>{movie.duration_minutes} min</strong>
        </div>
        <div className="catalog-movie-card__fact">
          <span>{t("sessionsCount")}</span>
          <strong>{sessionsCount}</strong>
        </div>
      </div>

      <div className="catalog-movie-card__schedule">
        {nextSession && lastSession ? (
          <div className="catalog-movie-card__sessions">
            <div className="catalog-movie-card__session">
              <span className="muted">{t("nextSession")}</span>
              <strong>{formatDateTime(nextSession.start_time)}</strong>
            </div>
            <div className="catalog-movie-card__session">
              <span className="muted">{t("lastUpcomingSession")}</span>
              <strong>{formatDateTime(lastSession.start_time)}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">{t("noUpcomingSessionsShort")}</p>
        )}
      </div>

      <div className="actions-row">
        <Link to={`/movies/${movie.id}`} className="button">
          {t("movieDetailsAction")}
        </Link>
        {nextSession ? (
          <Link to={`/schedule?movieId=${movie.id}`} className="button--ghost">
            {t("browseMovieSessions")}
          </Link>
        ) : null}
      </div>
    </article>
  );
}
