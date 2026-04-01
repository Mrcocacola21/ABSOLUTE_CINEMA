import { useTranslation } from "react-i18next";

import type { MovieCreatePayload } from "@/api/admin";
import { GENRE_OPTIONS, getGenreLabel, getGenreLabels } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import {
  getMovieStatusBadgeClassName,
  isMovieScheduleReady,
} from "@/shared/movieStatus";
import { formatStateLabel } from "@/shared/presentation";
import type { Movie } from "@/types/domain";
import { getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

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
  const { i18n } = useTranslation();
  const statusOptions =
    editingMovieId && movieForm.status === "active"
      ? [
          { value: "planned", label: "Planned" },
          { value: "active", label: "Active (automatic)" },
          { value: "deactivated", label: "Deactivated" },
        ]
      : [
          { value: "planned", label: "Planned" },
          { value: "deactivated", label: "Deactivated" },
        ];

  return (
    <section className="form-card admin-zone">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">Movie Management</p>
          <h2 className="section-title">Maintain the movie catalog</h2>
          <p className="muted">
            Build the lineup here first. Planned and active titles stay available in the planning shelf.
          </p>
        </div>
        <div className="stats-row">
          <span className="badge">{scheduleReadyMoviesCount} schedule-ready</span>
          <span className="badge">{statusCounts.planned} planned</span>
          <span className="badge">{statusCounts.active} active</span>
          <span className="badge">{statusCounts.deactivated} deactivated</span>
          <span className="badge">{totalMoviesCount} total titles</span>
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
              <p className="page-eyebrow">{editingMovieId ? "Editing movie" : "New movie"}</p>
              <h3 className="section-title">
                {editingMovieId ? "Update movie details" : "Add a title to the catalog"}
              </h3>
            </div>
            {editingMovieId ? (
              <button className="button--ghost" type="button" disabled={isBusy} onClick={onResetForm}>
                Clear form
              </button>
            ) : null}
          </div>

          {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

          <div className="form-grid">
            <label className="field">
              <span>Title (UK)</span>
              <input
                required
                disabled={isBusy}
                value={movieForm.title.uk}
                onChange={(event) => onLocalizedMovieFormChange("title", "uk", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Title (EN)</span>
              <input
                required
                disabled={isBusy}
                value={movieForm.title.en}
                onChange={(event) => onLocalizedMovieFormChange("title", "en", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Duration, min</span>
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
              <span>Age rating</span>
              <input
                disabled={isBusy}
                value={movieForm.age_rating ?? ""}
                onChange={(event) => onMovieFormChange("age_rating", event.target.value || undefined)}
              />
            </label>
            <label className="field field--wide">
              <span>Description (UK)</span>
              <textarea
                required
                disabled={isBusy}
                value={movieForm.description.uk}
                onChange={(event) => onLocalizedMovieFormChange("description", "uk", event.target.value)}
              />
            </label>
            <label className="field field--wide">
              <span>Description (EN)</span>
              <textarea
                required
                disabled={isBusy}
                value={movieForm.description.en}
                onChange={(event) => onLocalizedMovieFormChange("description", "en", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Poster URL</span>
              <input
                type="url"
                disabled={isBusy}
                value={movieForm.poster_url ?? ""}
                onChange={(event) => onMovieFormChange("poster_url", event.target.value || undefined)}
              />
            </label>
            <label className="field">
              <span>Status</span>
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
              <span>Genres</span>
              <div className="stats-row">
                {GENRE_OPTIONS.map((option) => (
                  <label key={option.code} className="badge">
                    <input
                      type="checkbox"
                      disabled={isBusy}
                      checked={movieForm.genres.includes(option.code)}
                      onChange={() => onToggleGenre(option.code)}
                    />{" "}
                    {getGenreLabel(option.code, i18n.language)}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <p className="field__hint">
            Planned titles are ready for scheduling. A movie becomes active automatically after it gets a future
            session. Deactivated titles stay in the catalog but are excluded from planning.
          </p>

          <div className="actions-row">
            <button className="button" type="submit" disabled={isBusy}>
              {isBusy ? "Saving..." : editingMovieId ? "Save movie changes" : "Create movie"}
            </button>
          </div>
        </form>

        <section className="admin-zone__catalog">
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">Catalog</p>
              <h3 className="section-title">Current lineup</h3>
            </div>
            <span className="badge">{catalogMovies.length}</span>
          </div>

          <label className="field">
            <span>Filter movies</span>
            <input
              value={movieQuery}
              onChange={(event) => onMovieQueryChange(event.target.value)}
              placeholder="Search by title, genre, rating, or description"
            />
          </label>

          <div className="admin-catalog__list">
            {catalogMovies.map((movie) => {
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
                      <span className="admin-catalog__duration">{movie.duration_minutes} min</span>
                    </div>
                  </div>

                  <div className="actions-row">
                    <button className="button--ghost" type="button" disabled={isBusy} onClick={() => onEditMovie(movie)}>
                      Edit movie
                    </button>
                    <button
                      className="button--ghost"
                      type="button"
                      disabled={isBusy || !isMovieScheduleReady(movie)}
                      onClick={() => onQueueMovie(movie)}
                    >
                      Queue for board
                    </button>
                    {movie.status === "deactivated" ? (
                      <button
                        className="button--ghost"
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onReturnToPlanned(movie)}
                      >
                        Return to planned
                      </button>
                    ) : (
                      <button
                        className="button--ghost"
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onDeactivateMovie(movie)}
                      >
                        Deactivate
                      </button>
                    )}
                    <button
                      className="button--danger"
                      type="button"
                      disabled={isBusy}
                      onClick={() => void onDeleteMovie(movie)}
                    >
                      Delete movie
                    </button>
                  </div>
                </article>
              );
            })}

            {catalogMovies.length === 0 ? (
              <section className="empty-state empty-state--panel">
                <h2>No movies found</h2>
                <p>Adjust the filter or create a new movie to begin scheduling.</p>
              </section>
            ) : null}
          </div>
        </section>
      </div>
    </section>
  );
}
