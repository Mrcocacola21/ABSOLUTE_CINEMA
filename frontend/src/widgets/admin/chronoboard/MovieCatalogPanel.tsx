import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { MovieCreatePayload } from "@/api/admin";
import { buildGenreSearchText, GENRE_OPTIONS, getGenreLabel, getGenreLabels } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import {
  getMovieStatusBadgeClassName,
  isMovieScheduleReady,
} from "@/shared/movieStatus";
import { usePagination } from "@/shared/pagination";
import { formatStateLabel } from "@/shared/presentation";
import { PaginationControls } from "@/shared/ui/PaginationControls";
import type { Movie } from "@/types/domain";
import { getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

const ADMIN_CATALOG_PAGE_SIZE = 5;

interface MovieCatalogPanelProps {
  catalogMovies: Movie[];
  totalMoviesCount: number;
  scheduleReadyMoviesCount: number;
  statusCounts: {
    planned: number;
    active: number;
    deactivated: number;
  };
  isBusy: boolean;
  busyActionLabel?: string;
  movieForm: MovieCreatePayload;
  editingMovieId: string | null;
  movieQuery: string;
  onMovieFormChange: <K extends keyof MovieCreatePayload>(field: K, value: MovieCreatePayload[K]) => void;
  onLocalizedMovieFormChange: (
    field: "title" | "description",
    locale: "uk" | "en",
    value: string,
  ) => void;
  onToggleGenre: (genre: MovieCreatePayload["genres"][number]) => void;
  onMovieQueryChange: (value: string) => void;
  onSubmit: () => Promise<void> | void;
  onResetForm: () => void;
  onEditMovie: (movie: Movie) => void;
  onQueueMovie: (movie: Movie) => void;
  onDeactivateMovie: (movie: Movie) => Promise<void> | void;
  onReturnToPlanned: (movie: Movie) => Promise<void> | void;
  onDeleteMovie: (movie: Movie) => Promise<void> | void;
}

export function MovieCatalogPanel({
  catalogMovies,
  totalMoviesCount,
  scheduleReadyMoviesCount,
  statusCounts,
  isBusy,
  busyActionLabel,
  movieForm,
  editingMovieId,
  movieQuery,
  onMovieFormChange,
  onLocalizedMovieFormChange,
  onToggleGenre,
  onMovieQueryChange,
  onSubmit,
  onResetForm,
  onEditMovie,
  onQueueMovie,
  onDeactivateMovie,
  onReturnToPlanned,
  onDeleteMovie,
}: MovieCatalogPanelProps) {
  const { t, i18n } = useTranslation();
  const [genreQuery, setGenreQuery] = useState("");
  const catalogPagination = usePagination(catalogMovies, {
    pageSize: ADMIN_CATALOG_PAGE_SIZE,
    resetKey: movieQuery.trim().toLowerCase(),
  });
  const selectedGenresCount = movieForm.genres.length;
  const normalizedGenreQuery = genreQuery.trim().toLowerCase();
  const visibleGenreOptions = GENRE_OPTIONS.filter((option) =>
    normalizedGenreQuery ? buildGenreSearchText(option.code).includes(normalizedGenreQuery) : true,
  );
  const statusOptions =
    editingMovieId && movieForm.status === "active"
      ? [
          { value: "planned", label: t("admin.movies.statusOptions.planned") },
          { value: "active", label: t("admin.movies.statusOptions.activeAutomatic") },
          { value: "deactivated", label: t("admin.movies.statusOptions.deactivated") },
        ]
      : [
          { value: "planned", label: t("admin.movies.statusOptions.planned") },
          { value: "deactivated", label: t("admin.movies.statusOptions.deactivated") },
        ];

  return (
    <section className="form-card admin-zone">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">{t("admin.movies.eyebrow")}</p>
          <h2 className="section-title">{t("admin.movies.title")}</h2>
          <p className="muted">{t("admin.movies.intro")}</p>
        </div>
        <div className="stats-row">
          <span className="badge">{scheduleReadyMoviesCount} {t("common.stats.scheduleReady")}</span>
          <span className="badge">{statusCounts.planned} {t("common.states.planned")}</span>
          <span className="badge">{statusCounts.active} {t("common.states.active")}</span>
          <span className="badge">{statusCounts.deactivated} {t("common.states.deactivated")}</span>
          <span className="badge">{totalMoviesCount} {t("common.stats.totalTitles")}</span>
        </div>
      </div>

      <div className="admin-zone__layout">
        <form
          className="admin-form admin-zone__form"
          onSubmit={(event) => {
            event.preventDefault();
            void onSubmit();
          }}
        >
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">
                {editingMovieId ? t("admin.movies.form.editEyebrow") : t("admin.movies.form.newEyebrow")}
              </p>
              <h3 className="section-title">
                {editingMovieId ? t("admin.movies.form.editTitle") : t("admin.movies.form.createTitle")}
              </h3>
            </div>
            {editingMovieId ? (
              <button className="button--ghost" type="button" disabled={isBusy} onClick={onResetForm}>
                {t("common.actions.clearForm")}
              </button>
            ) : null}
          </div>

          {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

          <div className="form-grid">
            <label className="field">
              <span>{t("common.labels.titleUk")}</span>
              <input
                required
                disabled={isBusy}
                value={movieForm.title.uk}
                onChange={(event) => onLocalizedMovieFormChange("title", "uk", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.titleEn")}</span>
              <input
                required
                disabled={isBusy}
                value={movieForm.title.en}
                onChange={(event) => onLocalizedMovieFormChange("title", "en", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.durationMinutes")}</span>
              <input
                required
                min={1}
                max={600}
                type="number"
                disabled={isBusy}
                value={movieForm.duration_minutes}
                onChange={(event) => onMovieFormChange("duration_minutes", Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.ageRating")}</span>
              <input
                disabled={isBusy}
                value={movieForm.age_rating ?? ""}
                onChange={(event) => onMovieFormChange("age_rating", event.target.value || undefined)}
              />
            </label>
            <label className="field field--wide">
              <span>{t("common.labels.descriptionUk")}</span>
              <textarea
                required
                disabled={isBusy}
                value={movieForm.description.uk}
                onChange={(event) => onLocalizedMovieFormChange("description", "uk", event.target.value)}
              />
            </label>
            <label className="field field--wide">
              <span>{t("common.labels.descriptionEn")}</span>
              <textarea
                required
                disabled={isBusy}
                value={movieForm.description.en}
                onChange={(event) => onLocalizedMovieFormChange("description", "en", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.posterUrl")}</span>
              <input
                type="url"
                disabled={isBusy}
                value={movieForm.poster_url ?? ""}
                onChange={(event) => onMovieFormChange("poster_url", event.target.value || undefined)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.status")}</span>
              <select
                disabled={isBusy}
                value={movieForm.status}
                onChange={(event) => onMovieFormChange("status", event.target.value as MovieCreatePayload["status"])}
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="field field--wide">
              <div className="admin-form__field-header">
                <span>{t("common.labels.genres")}</span>
                <span className="badge">{t("admin.movies.selectedCount", { count: selectedGenresCount })}</span>
              </div>
              <div className="admin-form__genre-toolbar">
                <label className="field admin-form__genre-search">
                  <span>{t("admin.movies.form.findGenreLabel")}</span>
                  <input
                    disabled={isBusy}
                    value={genreQuery}
                    onChange={(event) => setGenreQuery(event.target.value)}
                    placeholder={t("admin.movies.form.findGenrePlaceholder")}
                  />
                </label>
                <div className="admin-form__genre-selected">
                  <span className="admin-form__genre-selected-label">{t("common.labels.selectedGenres")}</span>
                  {selectedGenresCount > 0 ? (
                    <div className="admin-form__genre-tags">
                      {movieForm.genres.map((genre) => (
                        <button
                          key={genre}
                          className="admin-form__genre-tag"
                          type="button"
                          disabled={isBusy}
                          onClick={() => onToggleGenre(genre)}
                        >
                          {getGenreLabel(genre, i18n.language)}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="field__hint">{t("common.hints.selectedGenresAppearHere")}</p>
                  )}
                </div>
              </div>
              <div className="admin-form__genre-picker">
                {visibleGenreOptions.length > 0 ? (
                  visibleGenreOptions.map((option) => (
                    <label
                      key={option.code}
                      className={`admin-form__genre-option${movieForm.genres.includes(option.code) ? " is-selected" : ""}`}
                    >
                      <input
                        type="checkbox"
                        disabled={isBusy}
                        checked={movieForm.genres.includes(option.code)}
                        onChange={() => onToggleGenre(option.code)}
                      />
                      <span className="admin-form__genre-check" aria-hidden="true" />
                      <span>{getGenreLabel(option.code, i18n.language)}</span>
                    </label>
                  ))
                ) : (
                  <p className="admin-form__genre-empty">{t("common.hints.noGenresMatch")}</p>
                )}
              </div>
            </div>
          </div>

          <p className="field__hint">{t("admin.movies.form.statusHint")}</p>

          <div className="actions-row">
            <button className="button" type="submit" disabled={isBusy}>
              {isBusy
                ? `${t("common.actions.saveChanges")}...`
                : editingMovieId
                  ? t("common.actions.saveMovieChanges")
                  : t("common.actions.createMovie")}
            </button>
          </div>
        </form>

        <section className="admin-zone__catalog">
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">{t("admin.movies.catalogEyebrow")}</p>
              <h3 className="section-title">{t("common.labels.currentLineup")}</h3>
            </div>
            <span className="badge">{catalogMovies.length}</span>
          </div>

          <label className="field">
            <span>{t("admin.movies.filterLabel")}</span>
            <input
              value={movieQuery}
              onChange={(event) => onMovieQueryChange(event.target.value)}
              placeholder={t("admin.movies.filterPlaceholder")}
            />
          </label>

          <div className="admin-catalog__list">
            {catalogPagination.pageItems.map((movie) => {
              const movieTitle = getLocalizedText(movie.title, i18n.language);
              const movieDescription = getLocalizedText(movie.description, i18n.language);
              const genreLabel = getGenreLabels(movie.genres, i18n.language).join(", ");

              return (
                <article key={movie.id} className="card admin-catalog__card">
                  <div className="admin-card__header">
                    <div className="admin-catalog__media">
                      <div className="media-tile" aria-hidden="true">
                        {movie.poster_url ? (
                          <img src={movie.poster_url} alt="" className="media-tile__image" />
                        ) : (
                          <span>{getMovieMonogram(movieTitle)}</span>
                        )}
                      </div>
                      <div className="admin-catalog__copy">
                        <strong className="admin-catalog__title">{movieTitle}</strong>
                        <div className="admin-catalog__badges">
                          {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                          {movie.genres.length > 0 ? <span className="badge">{genreLabel}</span> : null}
                        </div>
                        <p className="muted">{movieDescription}</p>
                      </div>
                    </div>
                    <div className="admin-catalog__status-panel">
                      <span className={getMovieStatusBadgeClassName(movie.status)}>
                        {formatStateLabel(movie.status)}
                      </span>
                      <span className="admin-catalog__duration">
                        {movie.duration_minutes} {t("common.units.minutesShort")}
                      </span>
                    </div>
                  </div>

                  <div className="actions-row">
                    <button className="button--ghost" type="button" disabled={isBusy} onClick={() => onEditMovie(movie)}>
                      {t("common.actions.editMovie")}
                    </button>
                    <button
                      className="button--ghost"
                      type="button"
                      disabled={isBusy || !isMovieScheduleReady(movie)}
                      onClick={() => onQueueMovie(movie)}
                    >
                      {t("common.actions.queueForBoard")}
                    </button>
                    {movie.status === "deactivated" ? (
                      <button
                        className="button--ghost"
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onReturnToPlanned(movie)}
                      >
                        {t("common.actions.returnToPlanned")}
                      </button>
                    ) : (
                      <button
                        className="button--ghost"
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onDeactivateMovie(movie)}
                      >
                        {t("common.actions.deactivate")}
                      </button>
                    )}
                    <button
                      className="button--danger"
                      type="button"
                      disabled={isBusy}
                      onClick={() => void onDeleteMovie(movie)}
                    >
                      {t("common.actions.deleteMovie")}
                    </button>
                  </div>
                </article>
              );
            })}

            {catalogMovies.length === 0 ? (
              <section className="empty-state empty-state--panel">
                <h2>{t("admin.movies.emptyTitle")}</h2>
                <p>{t("admin.movies.emptyText")}</p>
              </section>
            ) : null}
          </div>

          <PaginationControls
            page={catalogPagination.page}
            totalPages={catalogPagination.totalPages}
            onPageChange={catalogPagination.setPage}
          />
        </section>
      </div>
    </section>
  );
}
