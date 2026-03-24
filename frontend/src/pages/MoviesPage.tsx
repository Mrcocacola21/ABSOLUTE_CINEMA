import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";

type StatusFilter = "all" | "active" | "inactive";

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

export function MoviesPage() {
  const { t } = useTranslation();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadMoviesCatalog() {
    setIsLoading(true);
    try {
      const [moviesResponse, scheduleResponse] = await Promise.all([
        getMoviesRequest({ includeInactive: true }),
        getScheduleRequest({
          sortBy: "start_time",
          sortOrder: "asc",
          limit: "100",
          offset: "0",
        }),
      ]);
      setMovies(moviesResponse.data);
      setItems(scheduleResponse.data);
      setErrorMessage("");
    } catch (error) {
      setMovies([]);
      setItems([]);
      setErrorMessage(extractApiErrorMessage(error, t("movieCatalogUnavailable")));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadMoviesCatalog();
  }, [t]);

  const sessionsByMovieId = useMemo(() => {
    const grouped = new Map<string, ScheduleItem[]>();

    for (const item of items) {
      const existingItems = grouped.get(item.movie_id) ?? [];
      existingItems.push(item);
      grouped.set(item.movie_id, existingItems);
    }

    for (const sessions of grouped.values()) {
      sessions.sort((left, right) => {
        return new Date(left.start_time).getTime() - new Date(right.start_time).getTime();
      });
    }

    return grouped;
  }, [items]);

  const genreOptions = useMemo(() => {
    const normalizedGenres = new Set<string>();

    for (const movie of movies) {
      for (const currentGenre of movie.genres) {
        normalizedGenres.add(currentGenre);
      }
    }

    return [...normalizedGenres].sort((left, right) => left.localeCompare(right));
  }, [movies]);

  const filteredMovies = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return [...movies]
      .filter((movie) => {
        if (status === "active" && !movie.is_active) {
          return false;
        }
        if (status === "inactive" && movie.is_active) {
          return false;
        }
        if (genre && !movie.genres.includes(genre)) {
          return false;
        }
        if (!normalizedQuery) {
          return true;
        }
        return movie.title.toLowerCase().includes(normalizedQuery);
      })
      .sort((left, right) => {
        if (left.is_active !== right.is_active) {
          return left.is_active ? -1 : 1;
        }
        return left.title.localeCompare(right.title);
      });
  }, [genre, movies, query, status]);

  function resetFilters() {
    setQuery("");
    setGenre("");
    setStatus("all");
  }

  return (
    <>
      <section className="page-header">
        <div>
          <p className="page-eyebrow">{t("catalogEyebrow")}</p>
          <h1 className="page-title">{t("movieCatalogTitle")}</h1>
          <p className="page-subtitle">{t("catalogIntro")}</p>
        </div>
        <div className="stats-row">
          <span className="badge">
            {movies.length} {t("movies")}
          </span>
          <span className="badge">
            {movies.filter((movie) => movie.is_active).length} {t("activeLabel")}
          </span>
          <span className="badge">
            {items.length} {t("upcomingSessions")}
          </span>
        </div>
      </section>

      {!isLoading ? (
        <section className="panel toolbar-panel">
          <div className="toolbar-panel__header">
            <div>
              <p className="page-eyebrow">{t("filters")}</p>
              <h2 className="section-title">{t("browseControls")}</h2>
            </div>
            <p className="toolbar-panel__summary">
              {t("catalogResultsLabel", {
                movies: filteredMovies.length,
                genres: genreOptions.length,
              })}
            </p>
          </div>

          <div className="toolbar toolbar--catalog">
            <label className="field field--search">
              <span>{t("searchByTitle")}</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("searchPlaceholder")}
              />
            </label>
            <label className="field">
              <span>{t("genre")}</span>
              <select value={genre} onChange={(event) => setGenre(event.target.value)}>
                <option value="">{t("allGenres")}</option>
                {genreOptions.map((currentGenre) => (
                  <option key={currentGenre} value={currentGenre}>
                    {currentGenre}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("status")}</span>
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as StatusFilter)}
              >
                <option value="all">{t("allStatuses")}</option>
                <option value="active">{t("activeOnly")}</option>
                <option value="inactive">{t("inactiveOnly")}</option>
              </select>
            </label>
            <div className="toolbar__actions">
              <button className="button--ghost" type="button" onClick={resetFilters}>
                {t("resetFilters")}
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading the movie catalog"
          message="Fetching movies and upcoming sessions."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title="Unable to load the movie catalog"
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadMoviesCatalog()}>
              Try again
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage && filteredMovies.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("catalogEmptyTitle")}</h2>
          <p>{t("catalogEmptyText")}</p>
          <button className="button--ghost" type="button" onClick={resetFilters}>
            {t("resetFilters")}
          </button>
        </section>
      ) : null}

      {!isLoading && !errorMessage && filteredMovies.length > 0 ? (
        <section className="cards-grid">
          {filteredMovies.map((movie) => {
            const sessions = sessionsByMovieId.get(movie.id) ?? [];
            const nextSession = sessions[0];
            const lastSession = sessions[sessions.length - 1];

            return (
              <article key={movie.id} className="card movie-card">
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
                      {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                    </div>
                    <h3>{movie.title}</h3>
                    <p className="muted">{movie.description}</p>
                  </div>
                </div>

                <div className="stats-row">
                  <span className="badge">
                    {t("duration")}: {movie.duration_minutes} min
                  </span>
                  {movie.genres.length > 0 ? <span className="badge">{movie.genres.join(", ")}</span> : null}
                  <span className="badge">
                    {t("sessionsCount")}: {sessions.length}
                  </span>
                </div>

                <div className="movie-card__schedule">
                  {nextSession ? (
                    <div className="schedule-range">
                      <div>
                        <span className="muted">{t("nextSession")}</span>
                        <strong>{formatDateTime(nextSession.start_time)}</strong>
                      </div>
                      <div>
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
          })}
        </section>
      ) : null}
    </>
  );
}
