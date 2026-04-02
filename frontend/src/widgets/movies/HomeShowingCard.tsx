import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getGenreLabel } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatDateTime, formatTime } from "@/shared/presentation";
import type { RotationMovie } from "@/shared/scheduleBrowse";

interface HomeShowingCardProps {
  movie: RotationMovie;
}

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatSessionRange(startTime: string, endTime: string): string {
  const start = new Date(startTime);
  const end = new Date(endTime);

  if (start.toDateString() === end.toDateString()) {
    return `${formatDateTime(startTime)}-${formatTime(endTime)}`;
  }

  return `${formatDateTime(startTime)} - ${formatDateTime(endTime)}`;
}

export function HomeShowingCard({ movie }: HomeShowingCardProps) {
  const { t, i18n } = useTranslation();
  const title = getLocalizedText(movie.title, i18n.language);
  const description = getLocalizedText(movie.description, i18n.language);

  return (
    <article className="card home-showing-card">
      <div className="home-showing-card__header">
        <Link to={`/movies/${movie.id}`} className="media-tile home-showing-card__media" aria-hidden="true">
          {movie.poster_url ? (
            <img src={movie.poster_url} alt="" className="media-tile__image" />
          ) : (
            <span>{getMovieMonogram(title)}</span>
          )}
        </Link>

        <div className="home-showing-card__copy">
          <h3 className="home-showing-card__title">{title}</h3>

          {movie.genres.length > 0 || movie.age_rating ? (
            <div className="meta-row home-showing-card__taxonomy">
              {movie.genres.map((genre) => (
                <span key={`${movie.id}-${genre}`} className="badge">
                  {getGenreLabel(genre, i18n.language)}
                </span>
              ))}
              {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
            </div>
          ) : null}

          <p className="muted home-showing-card__description">
            {description || t("home.spotlight.movieFallback")}
          </p>
        </div>
      </div>

      <div className="stats-row home-showing-card__stats">
        <span className="badge">
          {t("common.labels.upcomingSessions")}: {movie.upcomingSessions}
        </span>
        <span className="badge">
          {t("common.labels.availableSeats")}: {movie.maxAvailableSeats}
        </span>
        <span className="badge">
          {t("common.labels.price")}: {formatCurrency(movie.minPrice)}
        </span>
      </div>

      <div className="home-showing-card__schedule">
        <div className="home-showing-card__session">
          <span className="muted">{t("movie.sessionWindow.nextSession")}</span>
          <strong>{formatSessionRange(movie.nextSession.start_time, movie.nextSession.end_time)}</strong>
        </div>
        <div className="home-showing-card__session">
          <span className="muted">{t("movie.sessionWindow.lastUpcomingSession")}</span>
          <strong>{formatSessionRange(movie.lastSession.start_time, movie.lastSession.end_time)}</strong>
        </div>
      </div>

      <div className="actions-row">
        <Link to={`/schedule/${movie.nextSession.id}`} className="button">
          {t("common.actions.viewNextSession")}
        </Link>
        <Link to={`/movies/${movie.id}`} className="button--ghost">
          {t("common.actions.viewMovieDetails")}
        </Link>
      </div>
    </article>
  );
}
