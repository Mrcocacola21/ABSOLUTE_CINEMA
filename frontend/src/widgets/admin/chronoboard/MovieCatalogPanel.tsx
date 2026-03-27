import type { MovieCreatePayload } from "@/api/admin";
import type { Movie } from "@/types/domain";
import { getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

interface MovieCatalogPanelProps {
  catalogMovies: Movie[];
  totalMoviesCount: number;
  activeMoviesCount: number;
  isBusy: boolean;
  busyActionLabel?: string;
  movieForm: MovieCreatePayload;
  genresInput: string;
  editingMovieId: string | null;
  movieQuery: string;
  onMovieFormChange: <K extends keyof MovieCreatePayload>(field: K, value: MovieCreatePayload[K]) => void;
  onGenresInputChange: (value: string) => void;
  onMovieQueryChange: (value: string) => void;
  onSubmit: () => Promise<void> | void;
  onResetForm: () => void;
  onEditMovie: (movie: Movie) => void;
  onQueueMovie: (movie: Movie) => void;
  onDeactivateMovie: (movie: Movie) => Promise<void> | void;
  onDeleteMovie: (movie: Movie) => Promise<void> | void;
}

export function MovieCatalogPanel({
  catalogMovies,
  totalMoviesCount,
  activeMoviesCount,
  isBusy,
  busyActionLabel,
  movieForm,
  genresInput,
  editingMovieId,
  movieQuery,
  onMovieFormChange,
  onGenresInputChange,
  onMovieQueryChange,
  onSubmit,
  onResetForm,
  onEditMovie,
  onQueueMovie,
  onDeactivateMovie,
  onDeleteMovie,
}: MovieCatalogPanelProps) {
  return (
    <section className="form-card admin-zone">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">Movie Management</p>
          <h2 className="section-title">Maintain the movie catalog</h2>
          <p className="muted">
            Build the lineup here first. Active titles become available in the planning shelf.
          </p>
        </div>
        <div className="stats-row">
          <span className="badge">{activeMoviesCount} active titles</span>
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
              <span>Title</span>
              <input
                required
                disabled={isBusy}
                value={movieForm.title}
                onChange={(event) => onMovieFormChange("title", event.target.value)}
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
            <label className="field field--wide">
              <span>Description</span>
              <textarea
                required
                disabled={isBusy}
                value={movieForm.description}
                onChange={(event) => onMovieFormChange("description", event.target.value)}
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
            <label className="field">
              <span>Poster URL</span>
              <input
                type="url"
                disabled={isBusy}
                value={movieForm.poster_url ?? ""}
                onChange={(event) => onMovieFormChange("poster_url", event.target.value || undefined)}
              />
            </label>
            <label className="field field--wide">
              <span>Genres</span>
              <input
                disabled={isBusy}
                value={genresInput}
                onChange={(event) => onGenresInputChange(event.target.value)}
                placeholder="Drama, Comedy, Thriller"
              />
            </label>
            <label className="field field--checkbox">
              <input
                checked={movieForm.is_active}
                type="checkbox"
                disabled={isBusy}
                onChange={(event) => onMovieFormChange("is_active", event.target.checked)}
              />
              <span>Keep this title active for scheduling</span>
            </label>
          </div>

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
            {catalogMovies.map((movie) => (
              <article key={movie.id} className="card admin-catalog__card">
                <div className="admin-card__header">
                  <div className="admin-catalog__media">
                    <div className="media-tile" aria-hidden="true">
                      {movie.poster_url ? (
                        <img src={movie.poster_url} alt="" className="media-tile__image" />
                      ) : (
                        <span>{getMovieMonogram(movie.title)}</span>
                      )}
                    </div>
                    <div className="admin-catalog__copy">
                      <strong>{movie.title}</strong>
                      <p className="muted">{movie.description}</p>
                    </div>
                  </div>
                  <div className="stats-row">
                    <span className="badge">{movie.duration_minutes} min</span>
                    <span className={`badge${movie.is_active ? "" : " badge--danger"}`}>
                      {movie.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                </div>

                <div className="stats-row">
                  {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                  {movie.genres.length > 0 ? <span className="badge">{movie.genres.join(", ")}</span> : null}
                </div>

                <div className="actions-row">
                  <button className="button--ghost" type="button" disabled={isBusy} onClick={() => onEditMovie(movie)}>
                    Edit movie
                  </button>
                  <button
                    className="button--ghost"
                    type="button"
                    disabled={isBusy || !movie.is_active}
                    onClick={() => onQueueMovie(movie)}
                  >
                    Queue for board
                  </button>
                  <button
                    className="button--ghost"
                    type="button"
                    disabled={isBusy || !movie.is_active}
                    onClick={() => void onDeactivateMovie(movie)}
                  >
                    Deactivate
                  </button>
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
            ))}

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
