import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getGenreLabel } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import { getMovieStatusBadgeClassName } from "@/shared/movieStatus";
import { formatCurrency, formatTime } from "@/shared/presentation";
import type { Movie, ScheduleItem } from "@/types/domain";

type ActiveBannerProps = {
  variant: "active";
  movie: Movie;
  nextSession: ScheduleItem;
  upcomingSessions: number;
  minPrice: number;
};

type PlannedBannerProps = {
  variant: "planned";
  movie: Movie;
};

type HomeMovieBannerProps = ActiveBannerProps | PlannedBannerProps;

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatSessionSlot(startTime: string, endTime: string): string {
  const dateLabel = new Date(startTime).toLocaleDateString([], {
    day: "2-digit",
    month: "short",
  });

  return `${dateLabel}, ${formatTime(startTime)}-${formatTime(endTime)}`;
}

export function HomeMovieBanner(props: HomeMovieBannerProps) {
  const { t, i18n } = useTranslation();
  const { movie, variant } = props;
  const title = getLocalizedText(movie.title, i18n.language);
  const ribbonLabel = variant === "active" ? t("homeActiveRibbon") : t("homePlannedRibbon");
  const visibleGenres = movie.genres.slice(0, 5);

  const summaryLine =
    variant === "active"
      ? t("homeActiveBannerLine", {
          sessions: props.upcomingSessions,
          price: formatCurrency(props.minPrice),
        })
      : t("homePlannedBannerLine");

  const description =
    getLocalizedText(movie.description, i18n.language) ||
    (variant === "active" ? t("homeMovieFallback") : t("homePlannedFallback"));

  return (
    <article className={`home-poster-card home-poster-card--${variant}`}>
      <div className="home-poster-card__frame">
        <Link to={`/movies/${movie.id}`} className="home-poster-card__poster">
          {movie.poster_url ? (
            <img src={movie.poster_url} alt={title} className="home-poster-card__image" />
          ) : (
            <span className="home-poster-card__monogram">{getMovieMonogram(title)}</span>
          )}
        </Link>

        <div className="home-poster-card__topline">
          <span className={getMovieStatusBadgeClassName(movie.status)}>{t(`${movie.status}Label`)}</span>
          {movie.age_rating ? <span className="badge home-poster-card__age-rating">{movie.age_rating}</span> : null}
        </div>

        <div className={`home-poster-card__ribbon home-poster-card__ribbon--${variant}`}>{ribbonLabel}</div>

        <div className={`home-poster-card__overlay home-poster-card__overlay--${variant}`}>
          <div className={`home-poster-card__overlay-inner home-poster-card__overlay-inner--${variant}`}>
            <p className="home-poster-card__summary">{summaryLine}</p>

            <div className="home-poster-card__badges">
              {visibleGenres.map((genre) => (
                <span key={`${movie.id}-${genre}`} className="badge">
                  {getGenreLabel(genre, i18n.language)}
                </span>
              ))}
            </div>

            <p className="home-poster-card__description">{description}</p>

            {variant === "active" ? (
              <p className="home-poster-card__support">
                {t("nextSession")}: {formatSessionSlot(props.nextSession.start_time, props.nextSession.end_time)}
              </p>
            ) : (
              <p className="home-poster-card__support">{t("homePlannedFallback")}</p>
            )}

            <div className="home-poster-card__actions">
              {variant === "active" ? (
                <>
                  <Link to={`/schedule/${props.nextSession.id}`} className="button">
                    {t("viewNextSession")}
                  </Link>
                  <Link to={`/movies/${movie.id}`} className="button--ghost">
                    {t("movieDetailsAction")}
                  </Link>
                </>
              ) : (
                <>
                  <Link to={`/movies/${movie.id}`} className="button">
                    {t("movieDetailsAction")}
                  </Link>
                  <Link to="/movies" className="button--ghost">
                    {t("browseMovies")}
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="home-poster-card__caption">
        <h3 className="home-poster-card__title">
          <Link to={`/movies/${movie.id}`}>{title}</Link>
        </h3>
        <p className="home-poster-card__meta">
          {variant === "active"
            ? formatSessionSlot(props.nextSession.start_time, props.nextSession.end_time)
            : t("comingSoonTitle")}
        </p>
      </div>
    </article>
  );
}
