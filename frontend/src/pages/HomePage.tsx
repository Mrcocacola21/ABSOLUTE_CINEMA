import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { buildRotationMovies } from "@/shared/scheduleBrowse";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";
import { HomeMovieBanner } from "@/widgets/movies/HomeMovieBanner";

export function HomePage() {
  const { t } = useTranslation();
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
    () => buildRotationMovies(items, moviesById, "start_time", "asc"),
    [items, moviesById],
  );

  const plannedMovies = useMemo(
    () =>
      [...movies]
        .filter((movie) => movie.status === "planned")
        .sort((left, right) => left.title.localeCompare(right.title)),
    [movies],
  );

  const featuredPlannedMovie = plannedMovies[0] ?? null;

  return (
    <>
      <section className="page-header page-header--home home-hero">
        <div className="home-hero__copy">
          <p className="page-eyebrow">{t("brand")}</p>
          <h1 className="page-title">{t("homeHeroTitle")}</h1>
          <p className="page-subtitle">{t("homeHeroIntro")}</p>
          <div className="actions-row">
            <Link to="/movies" className="button--ghost">
              {t("browseMovies")}
            </Link>
            <Link to={role === "admin" ? "/admin" : "/schedule"} className="button">
              {role === "admin" ? t("openAdmin") : t("browseSchedule")}
            </Link>
          </div>
        </div>

        <div className="home-hero__aside">
          <div className="home-hero__metrics">
            <div className="home-hero__metric">
              <span>{t("activeLabel")}</span>
              <strong>{activeMovies.length}</strong>
            </div>
            <div className="home-hero__metric">
              <span>{t("plannedLabel")}</span>
              <strong>{plannedMovies.length}</strong>
            </div>
            <div className="home-hero__metric">
              <span>{t("upcomingSessions")}</span>
              <strong>{items.length}</strong>
            </div>
          </div>

          <div className="home-hero__note">
            <p className="page-eyebrow">{t("comingSoonEyebrow")}</p>
            <strong>{featuredPlannedMovie ? featuredPlannedMovie.title : t("comingSoonEmptyTitle")}</strong>
            <p className="muted">
              {featuredPlannedMovie
                ? featuredPlannedMovie.description || t("homePlannedFallback")
                : t("comingSoonEmptyText")}
            </p>
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
