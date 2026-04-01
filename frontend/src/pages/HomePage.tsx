import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getGenreLabel } from "@/shared/genres";
import { compareLocalizedText, getLocalizedText } from "@/shared/localization";
import { getMovieStatusBadgeClassName } from "@/shared/movieStatus";
import { formatCurrency, formatDateTime } from "@/shared/presentation";
import { buildRotationMovies } from "@/shared/scheduleBrowse";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";
import { HomeMovieBanner } from "@/widgets/movies/HomeMovieBanner";

export function HomePage() {
  const { t, i18n } = useTranslation();
  const { role } = useAuth();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadHomeData() {
    setIsLoading(true);
    try {
      const [scheduleResponse, moviesResponse] = await Promise.all([
        getScheduleRequest({
          sortBy: "start_time",
          sortOrder: "asc",
          limit: "100",
          offset: "0",
        }),
        getMoviesRequest({ includeInactive: true }),
      ]);
      setItems(scheduleResponse.data);
      setMovies(moviesResponse.data);
      setErrorMessage("");
    } catch (error) {
      setItems([]);
      setMovies([]);
      setErrorMessage(extractApiErrorMessage(error, t("backendScheduleUnavailable")));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadHomeData();
  }, [t]);

  const moviesById = useMemo(
    () => Object.fromEntries(movies.map((movie) => [movie.id, movie])),
    [movies],
  );

  const activeMovies = useMemo(
    () => buildRotationMovies(items, moviesById, "start_time", "asc", i18n.language),
    [i18n.language, items, moviesById],
  );

  const plannedMovies = useMemo(
    () =>
      [...movies]
        .filter((movie) => movie.status === "planned")
        .sort((left, right) => compareLocalizedText(left.title, right.title, i18n.language)),
    [i18n.language, movies],
  );

  const featuredActiveMovie = activeMovies[0] ?? null;
  const featuredPlannedMovie = plannedMovies[0] ?? null;
  const spotlightMovie = featuredActiveMovie ? (moviesById[featuredActiveMovie.id] ?? null) : featuredPlannedMovie;
  const spotlightVariant = featuredActiveMovie ? "active" : spotlightMovie ? "planned" : "empty";
  const spotlightDescription = spotlightMovie
    ? getLocalizedText(spotlightMovie.description, i18n.language) ||
      (featuredActiveMovie ? t("homeMovieFallback") : t("homePlannedFallback"))
    : t("comingSoonEmptyText");
  const spotlightSummary = featuredActiveMovie
    ? t("homeActiveBannerLine", {
        sessions: featuredActiveMovie.upcomingSessions,
        price: formatCurrency(featuredActiveMovie.minPrice),
      })
    : spotlightMovie
      ? t("homePlannedBannerLine")
      : t("comingSoonEmptyText");
  const spotlightMeta: string[] = spotlightMovie
    ? [
        spotlightMovie.age_rating,
        ...spotlightMovie.genres.slice(0, 2).map((genre) => getGenreLabel(genre, i18n.language)),
      ].filter(
        (item): item is string => Boolean(item),
      )
    : [];

  return (
    <>
      <section className="page-header page-header--home home-hero">
        <div className="home-hero__copy">
          <div className="home-hero__topline">
            <p className="page-eyebrow">{t("brand")}</p>
            <p className="home-hero__tagline">{t("brandTagline")}</p>
          </div>

          <div className="home-hero__lead">
            <h1 className="page-title">{t("homeHeroTitle")}</h1>
            <p className="page-subtitle">{t("homeHeroIntro")}</p>
          </div>

          <div className="actions-row home-hero__actions">
            <Link to="/movies" className="button--ghost">
              {t("browseMovies")}
            </Link>
            <Link to={role === "admin" ? "/admin" : "/schedule"} className="button">
              {role === "admin" ? t("openAdmin") : t("browseSchedule")}
            </Link>
          </div>

          <div className="home-hero__summary" aria-label={t("homeResultsLabel", { movies: movies.length, sessions: items.length })}>
            <div className="home-hero__summary-item">
              <span className="home-hero__summary-value">{activeMovies.length}</span>
              <span className="home-hero__summary-label">{t("activeLabel")}</span>
            </div>
            <div className="home-hero__summary-item">
              <span className="home-hero__summary-value">{plannedMovies.length}</span>
              <span className="home-hero__summary-label">{t("plannedLabel")}</span>
            </div>
            <div className="home-hero__summary-item">
              <span className="home-hero__summary-value">{items.length}</span>
              <span className="home-hero__summary-label">{t("upcomingSessions")}</span>
            </div>
          </div>
        </div>

        <div className={`home-hero__spotlight home-hero__spotlight--${spotlightVariant}`}>
          {spotlightMovie?.poster_url ? (
            <div
              className="home-hero__spotlight-backdrop"
              aria-hidden="true"
              style={{ backgroundImage: `url(${spotlightMovie.poster_url})` }}
            />
          ) : null}
          <div className="home-hero__spotlight-scrim" aria-hidden="true" />

          <div className="home-hero__spotlight-body">
            {spotlightMovie ? (
              <div className="home-hero__spotlight-topline">
                <span className={getMovieStatusBadgeClassName(spotlightMovie.status)}>
                  {t(`${spotlightMovie.status}Label`)}
                </span>
                {featuredActiveMovie ? (
                  <span className="badge home-hero__spotlight-session">
                    {formatDateTime(featuredActiveMovie.nextSession.start_time)}
                  </span>
                ) : null}
              </div>
            ) : null}

            <div className="home-hero__spotlight-copy">
              <p className="page-eyebrow">
                {featuredActiveMovie ? t("nowShowingEyebrow") : t("comingSoonEyebrow")}
              </p>
              <h2 className="home-hero__spotlight-title">
                {spotlightMovie ? getLocalizedText(spotlightMovie.title, i18n.language) : t("comingSoonEmptyTitle")}
              </h2>
              <p className="home-hero__spotlight-description">{spotlightDescription}</p>
            </div>

            {spotlightMeta.length > 0 ? (
              <div className="home-hero__spotlight-meta">
                {spotlightMeta.map((item) => (
                  <span key={item} className="badge">
                    {item}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="home-hero__spotlight-footer">
              <p className="home-hero__spotlight-summary">{spotlightSummary}</p>
              <Link
                to={
                  featuredActiveMovie
                    ? `/schedule/${featuredActiveMovie.nextSession.id}`
                    : spotlightMovie
                      ? `/movies/${spotlightMovie.id}`
                      : "/movies"
                }
                className="button--ghost home-hero__spotlight-action"
              >
                {featuredActiveMovie
                  ? t("viewNextSession")
                  : spotlightMovie
                    ? t("movieDetailsAction")
                    : t("browseMovies")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading the home page"
          message="Fetching active, planned, and upcoming movie data."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title="Unable to load the home page"
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadHomeData()}>
              Try again
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage ? (
        <div className="home-landing">
          <section className="panel home-section">
            <div className="home-section__header">
              <div>
                <p className="page-eyebrow">{t("nowShowingEyebrow")}</p>
                <h2 className="section-title">{t("nowShowingTitle")}</h2>
                <p className="home-section__intro">{t("nowShowingIntro")}</p>
              </div>
              <div className="stats-row">
                <span className="badge">
                  {activeMovies.length} {t("movies")}
                </span>
                <span className="badge">
                  {items.length} {t("upcomingSessions")}
                </span>
              </div>
            </div>

            {activeMovies.length > 0 ? (
              <div className="home-banner-grid">
                {activeMovies.map((movie) => {
                  const fullMovie = moviesById[movie.id];

                  if (!fullMovie) {
                    return null;
                  }

                  return (
                    <HomeMovieBanner
                      key={movie.id}
                      variant="active"
                      movie={fullMovie}
                      nextSession={movie.nextSession}
                      upcomingSessions={movie.upcomingSessions}
                      minPrice={movie.minPrice}
                    />
                  );
                })}
              </div>
            ) : (
              <section className="empty-state empty-state--panel">
                <h2>{t("homeActiveEmptyTitle")}</h2>
                <p>{t("homeActiveEmptyText")}</p>
              </section>
            )}
          </section>

          <section className="panel home-section home-section--planned">
            <div className="home-section__header">
              <div>
                <p className="page-eyebrow">{t("comingSoonEyebrow")}</p>
                <h2 className="section-title">{t("comingSoonTitle")}</h2>
                <p className="home-section__intro">{t("comingSoonIntro")}</p>
              </div>
              <div className="stats-row">
                <span className="badge">
                  {plannedMovies.length} {t("plannedLabel")}
                </span>
              </div>
            </div>

            {plannedMovies.length > 0 ? (
              <div className="home-banner-grid home-banner-grid--planned">
                {plannedMovies.map((movie) => (
                  <HomeMovieBanner key={movie.id} variant="planned" movie={movie} />
                ))}
              </div>
            ) : (
              <section className="empty-state empty-state--panel">
                <h2>{t("comingSoonEmptyTitle")}</h2>
                <p>{t("comingSoonEmptyText")}</p>
              </section>
            )}
          </section>
        </div>
      ) : null}
    </>
  );
}
