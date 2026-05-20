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
import { resolvePosterSource } from "@/shared/posters";
import { formatStateLabel } from "@/shared/presentation";
import { PaginationControls } from "@/shared/ui/PaginationControls";
import type { Movie } from "@/types/domain";
import { getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

const ADMIN_CATALOG_PAGE_SIZE = 5;
const MOVIE_TITLE_MAX_LENGTH = 150;
const MOVIE_DESCRIPTION_MAX_LENGTH = 2000;
const MOVIE_DURATION_MINUTES_MIN = 40;
const MOVIE_DURATION_MINUTES_MAX = 360;
const MOVIE_AGE_RATING_MAX_LENGTH = 16;

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
  moviePosterFile: File | null;
  moviePosterPreviewUrl: string | null;
  editingMovie: Movie | null;
  shouldRemoveMoviePoster: boolean;
  editingMovieId: string | null;
  movieQuery: string;
  onMovieFormChange: <K extends keyof MovieCreatePayload>(field: K, value: MovieCreatePayload[K]) => void;
  onLocalizedMovieFormChange: (
    field: "title" | "description",
    locale: "uk" | "en",
    value: string,
  ) => void;
  onToggleGenre: (genre: MovieCreatePayload["genres"][number]) => void;
  onMoviePosterFileChange: (file: File | null) => void;
  onMoviePosterRemovalChange: (shouldRemove: boolean) => void;
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
  moviePosterFile,
  moviePosterPreviewUrl,
  editingMovie,
  shouldRemoveMoviePoster,
  editingMovieId,
  movieQuery,
  onMovieFormChange,
  onLocalizedMovieFormChange,
  onToggleGenre,
  onMoviePosterFileChange,
  onMoviePosterRemovalChange,
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
  const posterFallbackSource = shouldRemoveMoviePoster
    ? movieForm.poster_url?.trim() || null
    : resolvePosterSource(editingMovie ?? { poster_url: movieForm.poster_url ?? null });
  const posterPreviewSource = moviePosterPreviewUrl ?? posterFallbackSource;
  const hasUploadedPoster = Boolean(editingMovie?.poster_file_url);
  const posterStatusLabel = moviePosterFile
    ? t("admin.movies.form.posterFileNew")
    : shouldRemoveMoviePoster
      ? t("admin.movies.form.posterFileRemovePending")
      : hasUploadedPoster
        ? t("admin.movies.form.posterFileUploaded")
        : t("admin.movies.form.posterFileFallback");
  const posterFileInputKey = `${editingMovieId ?? "new"}-${moviePosterFile?.name ?? "empty"}-${shouldRemoveMoviePoster}`;
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
                minLength={1}
                maxLength={MOVIE_TITLE_MAX_LENGTH}
                pattern=".*\S.*"
                disabled={isBusy}
                value={movieForm.title.uk}
                onChange={(event) => onLocalizedMovieFormChange("title", "uk", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.titleEn")}</span>
              <input
                required
                minLength={1}
                maxLength={MOVIE_TITLE_MAX_LENGTH}
                pattern=".*\S.*"
                disabled={isBusy}
                value={movieForm.title.en}
                onChange={(event) => onLocalizedMovieFormChange("title", "en", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.durationMinutes")}</span>
              <input
                required
                min={MOVIE_DURATION_MINUTES_MIN}
                max={MOVIE_DURATION_MINUTES_MAX}
                step={1}
                type="number"
                disabled={isBusy}
                value={movieForm.duration_minutes}
                onChange={(event) => onMovieFormChange("duration_minutes", Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.ageRating")}</span>
              <input
                maxLength={MOVIE_AGE_RATING_MAX_LENGTH}
                pattern="[A-Za-z0-9+ \-]*"
                disabled={isBusy}
                value={movieForm.age_rating ?? ""}
                onChange={(event) => onMovieFormChange("age_rating", event.target.value || undefined)}
              />
            </label>
            <label className="field field--wide">
              <span>{t("common.labels.descriptionUk")}</span>
              <textarea
                required
                minLength={1}
                maxLength={MOVIE_DESCRIPTION_MAX_LENGTH}
                disabled={isBusy}
                value={movieForm.description.uk}
                onChange={(event) => onLocalizedMovieFormChange("description", "uk", event.target.value)}
              />
            </label>
            <label className="field field--wide">
              <span>{t("common.labels.descriptionEn")}</span>
              <textarea
                required
                minLength={1}
                maxLength={MOVIE_DESCRIPTION_MAX_LENGTH}
                disabled={isBusy}
                value={movieForm.description.en}
                onChange={(event) => onLocalizedMovieFormChange("description", "en", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.posterUrl")}</span>
              <input
                type="text"
                inputMode="url"
                disabled={isBusy}
                value={movieForm.poster_url ?? ""}
                onChange={(event) => onMovieFormChange("poster_url", event.target.value || undefined)}
              />
            </label>
            <div className="field field--wide poster-upload-panel">
              <div className="admin-form__field-header">
                <span>{t("admin.movies.form.posterFileLabel")}</span>
                <span className="badge">{posterStatusLabel}</span>
              </div>
              <div className="poster-upload-panel__body">
                <div className="media-tile poster-upload-panel__preview" aria-hidden="true">
                  {posterPreviewSource ? (
                    <img src={posterPreviewSource} alt="" className="media-tile__image" />
                  ) : (
                    <span>{getMovieMonogram(movieForm.title.en || movieForm.title.uk || "Cinema")}</span>
                  )}
                </div>
                <div className="poster-upload-panel__controls">
                  <label className="field poster-upload-panel__file-field">
                    <span>{t("admin.movies.form.posterFileInput")}</span>
                    <input
                      key={posterFileInputKey}
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/svg+xml"
                      disabled={isBusy}
                      onChange={(event) => onMoviePosterFileChange(event.target.files?.[0] ?? null)}
                    />
                  </label>
                  <p className="field__hint">{t("admin.movies.form.posterFileHint")}</p>
                  <div className="actions-row poster-upload-panel__actions">
                    {moviePosterFile ? (
                      <button
                        className="button--ghost"
                        type="button"
                        disabled={isBusy}
                        onClick={() => onMoviePosterFileChange(null)}
                      >
                        {t("admin.movies.form.posterFileClearSelection")}
                      </button>
                    ) : null}
                    {hasUploadedPoster ? (
                      <button
                        className={shouldRemoveMoviePoster ? "button" : "button--ghost"}
                        type="button"
                        disabled={isBusy}
                        onClick={() => onMoviePosterRemovalChange(!shouldRemoveMoviePoster)}
                      >
                        {shouldRemoveMoviePoster
                          ? t("admin.movies.form.posterFileKeepUploaded")
                          : t("admin.movies.form.posterFileRemove")}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
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
              const posterSource = resolvePosterSource(movie);

              return (
                <article key={movie.id} className="card admin-catalog__card">
                  <div className="admin-card__header">
                    <div className="admin-catalog__media">
                      <div className="media-tile" aria-hidden="true">
                        {posterSource ? (
                          <img src={posterSource} alt="" className="media-tile__image" />
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
