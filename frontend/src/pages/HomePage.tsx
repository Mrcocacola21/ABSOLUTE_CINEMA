import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
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

const HOME_SECTION_PAGE_SIZE = 8;

function getTotalPages(itemsCount: number): number {
  return Math.max(1, Math.ceil(itemsCount / HOME_SECTION_PAGE_SIZE));
}

function getPageItems<T>(items: T[], page: number): T[] {
  const startIndex = (page - 1) * HOME_SECTION_PAGE_SIZE;
  return items.slice(startIndex, startIndex + HOME_SECTION_PAGE_SIZE);
}

export function HomePage() {
  const { t, i18n } = useTranslation();
  const { role } = useAuth();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [activePage, setActivePage] = useState(1);
  const [plannedPage, setPlannedPage] = useState(1);

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
      setErrorMessage(extractApiErrorMessage(error, t("schedule.errors.unavailable")));
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
  const activeTotalPages = useMemo(() => getTotalPages(activeMovies.length), [activeMovies.length]);
  const plannedTotalPages = useMemo(() => getTotalPages(plannedMovies.length), [plannedMovies.length]);
  const visibleActiveMovies = useMemo(
    () => getPageItems(activeMovies, activePage),
    [activeMovies, activePage],
  );
  const visiblePlannedMovies = useMemo(
    () => getPageItems(plannedMovies, plannedPage),
    [plannedMovies, plannedPage],
  );

  const featuredActiveMovie = activeMovies[0] ?? null;
  const featuredPlannedMovie = plannedMovies[0] ?? null;
  const spotlightMovie = featuredActiveMovie ? (moviesById[featuredActiveMovie.id] ?? null) : featuredPlannedMovie;
  const spotlightVariant = featuredActiveMovie ? "active" : spotlightMovie ? "planned" : "empty";
  const spotlightDescription = spotlightMovie
    ? getLocalizedText(spotlightMovie.description, i18n.language) ||
      (featuredActiveMovie ? t("home.spotlight.movieFallback") : t("home.spotlight.plannedFallback"))
    : t("home.sections.comingSoon.emptyText");
  const spotlightSummary = featuredActiveMovie
    ? t("home.spotlight.activeSummary", {
        sessions: featuredActiveMovie.upcomingSessions,
        price: formatCurrency(featuredActiveMovie.minPrice),
      })
    : spotlightMovie
      ? t("home.spotlight.plannedSummary")
      : t("home.sections.comingSoon.emptyText");
  const spotlightMeta: string[] = spotlightMovie
    ? [
        spotlightMovie.age_rating,
        ...spotlightMovie.genres.slice(0, 2).map((genre) => getGenreLabel(genre, i18n.language)),
      ].filter(
        (item): item is string => Boolean(item),
      )
    : [];

  useEffect(() => {
    setActivePage((currentPage) => Math.min(currentPage, activeTotalPages));
  }, [activeTotalPages]);

  useEffect(() => {
    setPlannedPage((currentPage) => Math.min(currentPage, plannedTotalPages));
  }, [plannedTotalPages]);

  function renderSectionPagination(
    page: number,
    totalPages: number,
    onPageChange: Dispatch<SetStateAction<number>>,
  ) {
    if (totalPages <= 1) {
      return null;
    }

    return (
      <div className="home-section__pagination">
        <button
          className="button--ghost"
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange((currentPage) => Math.max(1, currentPage - 1))}
        >
          {t("home.pagination.previous")}
        </button>
        <span className="home-section__pagination-label">
          {t("home.pagination.pageIndicator", { current: page, total: totalPages })}
        </span>
        <button
          className="button--ghost"
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange((currentPage) => Math.min(totalPages, currentPage + 1))}
        >
          {t("home.pagination.next")}
        </button>
      </div>
    );
  }

  return (
    <>
      <section className="page-header page-header--home home-hero">
        <div className="home-hero__copy">
          <div className="home-hero__topline">
            <p className="page-eyebrow">{t("common.brand.title")}</p>
            <p className="home-hero__tagline">{t("common.brand.tagline")}</p>
          </div>

          <div className="home-hero__lead">
            <h1 className="page-title">{t("home.hero.title")}</h1>
            <p className="page-subtitle">{t("home.hero.intro")}</p>
          </div>

          <div className="actions-row home-hero__actions">
            <Link to="/movies" className="button--ghost">
              {t("common.actions.browseMovies")}
            </Link>
            <Link to={role === "admin" ? "/admin" : "/schedule"} className="button">
              {role === "admin" ? t("common.actions.openAdmin") : t("common.actions.browseSchedule")}
            </Link>
          </div>

          <div
            className="home-hero__summary"
            aria-label={t("movies.catalog.resultsLabel", { movies: movies.length, genres: items.length })}
          >
            <div className="home-hero__summary-item">
              <span className="home-hero__summary-value">{activeMovies.length}</span>
              <span className="home-hero__summary-label">{t("common.states.active")}</span>
            </div>
            <div className="home-hero__summary-item">
              <span className="home-hero__summary-value">{plannedMovies.length}</span>
              <span className="home-hero__summary-label">{t("common.states.planned")}</span>
            </div>
            <div className="home-hero__summary-item">
              <span className="home-hero__summary-value">{items.length}</span>
              <span className="home-hero__summary-label">{t("common.labels.upcomingSessions")}</span>
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
                  {t(`common.states.${spotlightMovie.status}`)}
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
                {featuredActiveMovie ? t("home.sections.nowShowing.eyebrow") : t("home.sections.comingSoon.eyebrow")}
              </p>
              <h2 className="home-hero__spotlight-title">
                {spotlightMovie
                  ? getLocalizedText(spotlightMovie.title, i18n.language)
                  : t("home.sections.comingSoon.emptyTitle")}
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
                  ? t("common.actions.viewNextSession")
                  : spotlightMovie
                    ? t("common.actions.viewMovieDetails")
                    : t("common.actions.browseMovies")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      {isLoading ? (
        <StatePanel
          tone="loading"
          title={t("home.loading.title")}
          message={t("home.loading.message")}
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title={t("home.errors.title")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadHomeData()}>
              {t("common.actions.retry")}
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage ? (
        <div className="home-landing">
          <section className="panel home-section">
            <div className="home-section__header">
              <div>
                <p className="page-eyebrow">{t("home.sections.nowShowing.eyebrow")}</p>
                <h2 className="section-title">{t("home.sections.nowShowing.title")}</h2>
                <p className="home-section__intro">{t("home.sections.nowShowing.intro")}</p>
              </div>
              <div className="home-section__controls">
                <div className="stats-row">
                  <span className="badge">
                    {activeMovies.length} {t("common.labels.movies")}
                  </span>
                  <span className="badge">
                    {items.length} {t("common.labels.upcomingSessions")}
                  </span>
                </div>
                {renderSectionPagination(activePage, activeTotalPages, setActivePage)}
              </div>
            </div>

            {activeMovies.length > 0 ? (
              <div className="home-banner-grid">
                {visibleActiveMovies.map((movie) => {
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
                <h2>{t("home.sections.nowShowing.emptyTitle")}</h2>
                <p>{t("home.sections.nowShowing.emptyText")}</p>
              </section>
            )}
          </section>

          <section className="panel home-section home-section--planned">
            <div className="home-section__header">
              <div>
                <p className="page-eyebrow">{t("home.sections.comingSoon.eyebrow")}</p>
                <h2 className="section-title">{t("home.sections.comingSoon.title")}</h2>
                <p className="home-section__intro">{t("home.sections.comingSoon.intro")}</p>
              </div>
              <div className="home-section__controls">
                <div className="stats-row">
                  <span className="badge">
                    {plannedMovies.length} {t("common.states.planned")}
                  </span>
                </div>
                {renderSectionPagination(plannedPage, plannedTotalPages, setPlannedPage)}
              </div>
            </div>

            {plannedMovies.length > 0 ? (
              <div className="home-banner-grid home-banner-grid--planned">
                {visiblePlannedMovies.map((movie) => (
                  <HomeMovieBanner key={movie.id} variant="planned" movie={movie} />
                ))}
              </div>
            ) : (
              <section className="empty-state empty-state--panel">
                <h2>{t("home.sections.comingSoon.emptyTitle")}</h2>
                <p>{t("home.sections.comingSoon.emptyText")}</p>
              </section>
            )}
          </section>
        </div>
      ) : null}
    </>
  );
}
