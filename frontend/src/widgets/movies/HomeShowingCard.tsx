import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();

  return (
    <article className="card home-showing-card">
      <div className="home-showing-card__header">
        <Link to={`/movies/${movie.id}`} className="media-tile home-showing-card__media" aria-hidden="true">
          {movie.poster_url ? (
            <img src={movie.poster_url} alt="" className="media-tile__image" />
          ) : (
            <span>{getMovieMonogram(movie.title)}</span>
          )}
        </Link>

        <div className="home-showing-card__copy">
          <h3 className="home-showing-card__title">{movie.title}</h3>

          {movie.genres.length > 0 || movie.age_rating ? (
            <div className="meta-row home-showing-card__taxonomy">
              {movie.genres.map((genre) => (
                <span key={`${movie.id}-${genre}`} className="badge">
                  {genre}
                </span>
              ))}
              {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
            </div>
          ) : null}

          <p className="muted home-showing-card__description">
            {movie.description || t("homeMovieFallback")}
          </p>
        </div>
      </div>

      <div className="stats-row home-showing-card__stats">
        <span className="badge">
          {t("upcomingSessions")}: {movie.upcomingSessions}
        </span>
        <span className="badge">
          {t("availableSeats")}: {movie.maxAvailableSeats}
        </span>
        <span className="badge">
          {t("fromPrice")}: {formatCurrency(movie.minPrice)}
        </span>
      </div>

      <div className="home-showing-card__schedule">
        <div className="home-showing-card__session">
          <span className="muted">{t("nextSession")}</span>
          <strong>{formatSessionRange(movie.nextSession.start_time, movie.nextSession.end_time)}</strong>
        </div>
        <div className="home-showing-card__session">
          <span className="muted">{t("lastUpcomingSession")}</span>
          <strong>{formatSessionRange(movie.lastSession.start_time, movie.lastSession.end_time)}</strong>
        </div>
      </div>

      <div className="actions-row">
        <Link to={`/schedule/${movie.nextSession.id}`} className="button">
          {t("viewNextSession")}
        </Link>
        <Link to={`/movies/${movie.id}`} className="button--ghost">
          {t("movieDetailsAction")}
        </Link>
      </div>
    </article>
  );
}
