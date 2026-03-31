import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getMovieStatusPriority } from "@/shared/movieStatus";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, MovieStatus, ScheduleItem } from "@/types/domain";
import { MovieCatalogCard } from "@/widgets/movies/MovieCatalogCard";

type StatusFilter = "all" | MovieStatus;

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
        if (status !== "all" && movie.status !== status) {
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
        const statusComparison = getMovieStatusPriority(left.status) - getMovieStatusPriority(right.status);
        if (statusComparison !== 0) {
          return statusComparison;
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
            {movies.filter((movie) => movie.status === "active").length} {t("activeLabel")}
          </span>
          <span className="badge">
            {movies.filter((movie) => movie.status === "planned").length} {t("plannedLabel")}
          </span>
          <span className="badge">
            {movies.filter((movie) => movie.status === "deactivated").length} {t("deactivatedLabel")}
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
                <option value="planned">{t("plannedOnly")}</option>
                <option value="active">{t("activeOnly")}</option>
                <option value="deactivated">{t("deactivatedOnly")}</option>
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
        <section className="cards-grid movie-catalog-grid">
          {filteredMovies.map((movie) => {
            const sessions = sessionsByMovieId.get(movie.id) ?? [];
            const nextSession = sessions[0];
            const lastSession = sessions[sessions.length - 1];

            return (
              <MovieCatalogCard
                key={movie.id}
                movie={movie}
                sessionsCount={sessions.length}
                nextSession={nextSession}
                lastSession={lastSession}
              />
            );
          })}
        </section>
      ) : null}
    </>
  );
}
