import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getGenreLabel } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import { getMovieStatusTranslationKey } from "@/shared/movieStatus";
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
  const { t, i18n } = useTranslation();
  const title = getLocalizedText(movie.title, i18n.language);
  const description = getLocalizedText(movie.description, i18n.language);
  const statusClassName = `catalog-movie-card__status catalog-movie-card__status--${movie.status}`;

  return (
    <article className="card catalog-movie-card">
      <div className="catalog-movie-card__hero">
        <Link to={`/movies/${movie.id}`} className="media-tile catalog-movie-card__media" aria-hidden="true">
          {movie.poster_url ? (
            <img src={movie.poster_url} alt="" className="media-tile__image" />
          ) : (
            <span>{getMovieMonogram(title)}</span>
          )}
        </Link>

        <div className="catalog-movie-card__body">
          <div className="catalog-movie-card__topline">
            <div className="catalog-movie-card__title-row">
              <h3 className="catalog-movie-card__title">{title}</h3>
              <div className="catalog-movie-card__title-meta">
                <span className={statusClassName}>{t(getMovieStatusTranslationKey(movie.status))}</span>
                {movie.age_rating ? <span className="badge catalog-movie-card__age-rating">{movie.age_rating}</span> : null}
              </div>
            </div>

            {movie.genres.length > 0 ? (
              <div className="meta-row catalog-movie-card__taxonomy">
                {movie.genres.map((genre) => (
                  <span key={`${movie.id}-${genre}`} className="badge">
                    {getGenreLabel(genre, i18n.language)}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          {description ? (
            <p className="muted catalog-movie-card__description">{description}</p>
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
