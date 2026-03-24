import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import {
  buildRotationMovies,
  filterScheduleItems,
  getAvailableMovieOptions,
  sortScheduleItems,
} from "@/shared/scheduleBrowse";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";
import { ScheduleToolbar } from "@/widgets/schedule/ScheduleToolbar";

function formatCurrency(value: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "UAH",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function HomePage() {
  const { t } = useTranslation();
  const { role } = useAuth();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState("start_time");
  const [sortOrder, setSortOrder] = useState("asc");
  const [movieId, setMovieId] = useState("");
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
        getMoviesRequest(),
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

  const visibleItems = useMemo(
    () => items.filter((item) => Boolean(moviesById[item.movie_id]?.is_active)),
    [items, moviesById],
  );

  const availableMovieOptions = useMemo(
    () => getAvailableMovieOptions(visibleItems),
    [visibleItems],
  );

  const filteredItems = useMemo(
    () => filterScheduleItems(visibleItems, query, movieId),
    [movieId, query, visibleItems],
  );

  const sortedItems = useMemo(
    () => sortScheduleItems(filteredItems, sortBy, sortOrder),
    [filteredItems, sortBy, sortOrder],
  );

  const rotationMovies = useMemo(
    () => buildRotationMovies(sortedItems, moviesById, sortBy, sortOrder),
    [moviesById, sortBy, sortOrder, sortedItems],
  );

  function handleToolbarChange(key: string, value: string) {
    if (key === "query") {
      setQuery(value);
      return;
    }
    if (key === "sortBy") {
      setSortBy(value);
      return;
    }
    if (key === "sortOrder") {
      setSortOrder(value);
      return;
    }
    if (key === "movieId") {
      setMovieId(value);
    }
  }

  function resetFilters() {
    setQuery("");
    setSortBy("start_time");
    setSortOrder("asc");
    setMovieId("");
  }

  return (
    <>
      <section className="page-header page-header--home">
        <div>
          <p className="page-eyebrow">{t("nowShowingEyebrow")}</p>
          <h1 className="page-title">{t("nowShowingTitle")}</h1>
          <p className="page-subtitle">{t("nowShowingIntro")}</p>
        </div>
        <div className="stats-row">
          <span className="badge">
            {rotationMovies.length} {t("movies")}
          </span>
          <span className="badge">
            {visibleItems.length} {t("upcomingSessions")}
          </span>
          <Link to="/movies" className="button--ghost">
            {t("browseMovies")}
          </Link>
          <Link to={role === "admin" ? "/admin" : "/schedule"} className="button">
            {role === "admin" ? t("openAdmin") : t("browseSchedule")}
          </Link>
        </div>
      </section>

      {!isLoading && !errorMessage ? (
        <ScheduleToolbar
          query={query}
          sortBy={sortBy}
          sortOrder={sortOrder}
          movieId={movieId}
          movies={availableMovieOptions}
          resultsLabel={t("homeResultsLabel", {
            movies: rotationMovies.length,
            sessions: sortedItems.length,
          })}
          onChange={handleToolbarChange}
          onReset={resetFilters}
        />
      ) : null}

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading the home page"
          message="Fetching active movies and upcoming sessions."
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

      {!isLoading && !errorMessage && rotationMovies.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("homeEmptyTitle")}</h2>
          <p>{t("homeEmptyText")}</p>
          <button className="button--ghost" type="button" onClick={resetFilters}>
            {t("resetFilters")}
          </button>
        </section>
      ) : null}

      {!isLoading && !errorMessage && rotationMovies.length > 0 ? (
        <section className="cards-grid showing-grid">
          {rotationMovies.map((movie) => (
            <article key={movie.id} className="card showing-card movie-card">
              <div className="showing-card__header">
                <Link to={`/movies/${movie.id}`} className="media-tile showing-card__media" aria-hidden="true">
                  {movie.poster_url ? (
                    <img src={movie.poster_url} alt="" className="media-tile__image" />
                  ) : (
                    <span>{getMovieMonogram(movie.title)}</span>
                  )}
                </Link>
                <div className="showing-card__copy">
                  <div className="meta-row">
                    <span className="badge">{movie.is_active ? t("activeLabel") : t("inactiveLabel")}</span>
                    <span className="badge">{t("nextSession")}</span>
                    {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                  </div>
                  <h3>{movie.title}</h3>
                  <p className="muted">
                    {movie.description ?? t("homeMovieFallback")}
                  </p>
                </div>
              </div>

              <div className="stats-row">
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

              <div className="showing-card__schedule">
                <div className="schedule-range">
                  <div>
                    <span className="muted">{t("nextSession")}</span>
                    <strong>{formatDateTime(movie.nextSession.start_time)}</strong>
                  </div>
                  <div>
                    <span className="muted">{t("lastUpcomingSession")}</span>
                    <strong>{formatDateTime(movie.lastSession.start_time)}</strong>
                  </div>
                </div>
                <p className="muted">
                  {movie.genres.length > 0 ? movie.genres.join(", ") : t("currentlyShowing")}
                </p>
              </div>

              <div className="actions-row">
                <Link to={`/schedule/${movie.nextSession.id}`} className="button">
                  {t("viewSession")}
                </Link>
                <Link to={`/movies/${movie.id}`} className="button--ghost">
                  {t("movieDetailsAction")}
                </Link>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </>
  );
}
