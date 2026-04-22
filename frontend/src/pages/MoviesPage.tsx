import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getGenreLabel, type GenreCode } from "@/shared/genres";
import { compareLocalizedText } from "@/shared/localization";
import { getMovieStatusPriority } from "@/shared/movieStatus";
import { usePagination } from "@/shared/pagination";
import { buildMovieSearchText } from "@/shared/scheduleBrowse";
import { PaginationControls } from "@/shared/ui/PaginationControls";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, MovieStatus, ScheduleItem } from "@/types/domain";
import { MovieCatalogCard } from "@/widgets/movies/MovieCatalogCard";

type StatusFilter = "all" | MovieStatus;
const MOVIES_PAGE_SIZE = 9;

export function MoviesPage() {
  const { t, i18n } = useTranslation();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState<GenreCode | "">("");
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
      setErrorMessage(extractApiErrorMessage(error, t("movies.errors.unavailable")));
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
    const normalizedGenres = new Set<GenreCode>();

    for (const movie of movies) {
      for (const currentGenre of movie.genres) {
        normalizedGenres.add(currentGenre);
      }
    }

    return [...normalizedGenres].sort((left, right) =>
      getGenreLabel(left, i18n.language).localeCompare(getGenreLabel(right, i18n.language)),
    );
  }, [i18n.language, movies]);

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
        return buildMovieSearchText(movie).includes(normalizedQuery);
      })
      .sort((left, right) => {
        const statusComparison = getMovieStatusPriority(left.status) - getMovieStatusPriority(right.status);
        if (statusComparison !== 0) {
          return statusComparison;
        }
        return compareLocalizedText(left.title, right.title, i18n.language);
      });
  }, [genre, i18n.language, movies, query, status]);

  const moviesPagination = usePagination(filteredMovies, {
    pageSize: MOVIES_PAGE_SIZE,
    resetKey: JSON.stringify({ genre, query, status }),
  });

  function resetFilters() {
    setQuery("");
    setGenre("");
    setStatus("all");
  }

  return (
    <>
      <section className="page-header">
        <div>
          <p className="page-eyebrow">{t("movies.catalog.eyebrow")}</p>
          <h1 className="page-title">{t("movies.catalog.title")}</h1>
          <p className="page-subtitle">{t("movies.catalog.intro")}</p>
        </div>
        <div className="stats-row">
          <span className="badge">
            {movies.length} {t("common.labels.movies")}
          </span>
          <span className="badge">
            {movies.filter((movie) => movie.status === "active").length} {t("common.states.active")}
          </span>
          <span className="badge">
            {movies.filter((movie) => movie.status === "planned").length} {t("common.states.planned")}
          </span>
          <span className="badge">
            {movies.filter((movie) => movie.status === "deactivated").length} {t("common.states.deactivated")}
          </span>
          <span className="badge">
            {items.length} {t("common.labels.upcomingSessions")}
          </span>
        </div>
      </section>

      {!isLoading ? (
        <section className="panel toolbar-panel">
          <div className="toolbar-panel__header">
            <div>
              <p className="page-eyebrow">{t("common.labels.filters")}</p>
              <h2 className="section-title">{t("common.labels.browseControls")}</h2>
            </div>
            <p className="toolbar-panel__summary">
              {t("movies.catalog.resultsLabel", {
                movies: filteredMovies.length,
                genres: genreOptions.length,
              })}
            </p>
          </div>

          <div className="toolbar toolbar--catalog">
            <label className="field field--search">
              <span>{t("movies.filters.searchByTitle")}</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("movies.filters.searchPlaceholder")}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.genre")}</span>
              <select value={genre} onChange={(event) => setGenre(event.target.value as GenreCode | "")}>
                <option value="">{t("common.labels.allGenres")}</option>
                {genreOptions.map((currentGenre) => (
                  <option key={currentGenre} value={currentGenre}>
                    {getGenreLabel(currentGenre, i18n.language)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("common.labels.status")}</span>
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as StatusFilter)}
              >
                <option value="all">{t("movies.filters.allStatuses")}</option>
                <option value="planned">{t("movies.filters.plannedOnly")}</option>
                <option value="active">{t("movies.filters.activeOnly")}</option>
                <option value="deactivated">{t("movies.filters.deactivatedOnly")}</option>
              </select>
            </label>
            <div className="toolbar__actions">
              <button className="button--ghost" type="button" onClick={resetFilters}>
                {t("common.actions.resetFilters")}
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {isLoading ? (
        <StatePanel
          tone="loading"
          title={t("movies.loading.title")}
          message={t("movies.loading.message")}
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title={t("movies.errors.title")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadMoviesCatalog()}>
              {t("common.actions.retry")}
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage && filteredMovies.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("movies.catalog.emptyTitle")}</h2>
          <p>{t("movies.catalog.emptyText")}</p>
          <button className="button--ghost" type="button" onClick={resetFilters}>
            {t("common.actions.resetFilters")}
          </button>
        </section>
      ) : null}

      {!isLoading && !errorMessage && filteredMovies.length > 0 ? (
        <section className="catalog-results-stack">
          <section className="cards-grid movie-catalog-grid">
            {moviesPagination.pageItems.map((movie) => {
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

          <PaginationControls
            page={moviesPagination.page}
            totalPages={moviesPagination.totalPages}
            onPageChange={moviesPagination.setPage}
          />
        </section>
      ) : null}
    </>
  );
}
