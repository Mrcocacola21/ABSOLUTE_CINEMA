import type { DragEvent } from "react";

import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { Movie } from "@/types/domain";
import { getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

interface PlanningShelfProps {
  planningMovies: Movie[];
  plannerMovieQuery: string;
  selectedMovie: Movie | null;
  pinnedMovieId: string | null;
  draggedMovieId: string | null;
  isBusy: boolean;
  onPlannerMovieQueryChange: (value: string) => void;
  onSelectMovie: (movie: Movie) => void;
  onClearPlanningSelection: () => void;
  onDragStart: (event: DragEvent<HTMLElement>, movieId: string) => void;
  onDragEnd: () => void;
}

export function PlanningShelf({
  planningMovies,
  plannerMovieQuery,
  selectedMovie,
  pinnedMovieId,
  draggedMovieId,
  isBusy,
  onPlannerMovieQueryChange,
  onSelectMovie,
  onClearPlanningSelection,
  onDragStart,
  onDragEnd,
}: PlanningShelfProps) {
  return (
    <section className="card planning-shelf">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">Planning Shelf</p>
          <h3 className="section-title">Drag source / staging area</h3>
          <p className="muted">Pick an active title, then drag it onto the board to create a gray draft.</p>
        </div>
        <span className="badge">{planningMovies.length}</span>
      </div>

      <label className="field">
        <span>Find an active movie</span>
        <input
          value={plannerMovieQuery}
          onChange={(event) => onPlannerMovieQueryChange(event.target.value)}
          placeholder="Search active titles"
        />
      </label>

      {selectedMovie ? (
        <StatusBanner
          tone="info"
          title="Selected movie"
          message={`${selectedMovie.title} is queued for board placement. Drag it or click a free slot on the timeline.`}
          action={
            <button className="button--ghost" type="button" onClick={onClearPlanningSelection}>
              Clear
            </button>
          }
        />
      ) : null}

      <div className="planning-shelf__grid">
        {planningMovies.map((movie) => {
          const isSelected = movie.id === pinnedMovieId || movie.id === draggedMovieId;

          return (
            <article
              key={movie.id}
              className={`admin-source-card${isSelected ? " is-selected" : ""}`}
              draggable={!isBusy}
              onDragStart={(event) => onDragStart(event, movie.id)}
              onDragEnd={onDragEnd}
            >
              <div className="admin-source-card__header">
                <div className="media-tile admin-source-card__media" aria-hidden="true">
                  {movie.poster_url ? (
                    <img src={movie.poster_url} alt="" className="media-tile__image" />
                  ) : (
                    <span>{getMovieMonogram(movie.title)}</span>
                  )}
                </div>
                <div>
                  <strong>{movie.title}</strong>
                  <p className="muted">{movie.duration_minutes} min</p>
                </div>
              </div>
              <div className="stats-row">
                {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                {movie.genres.length > 0 ? <span className="badge">{movie.genres.join(", ")}</span> : null}
              </div>
              <div className="actions-row">
                <button className="button--ghost" type="button" disabled={isBusy} onClick={() => onSelectMovie(movie)}>
                  Select
                </button>
              </div>
            </article>
          );
        })}

        {planningMovies.length === 0 ? (
          <section className="empty-state empty-state--panel">
            <h2>No active movies ready</h2>
            <p>Activate or create a movie first, then drag it from the shelf onto the board.</p>
          </section>
        ) : null}
      </div>
    </section>
  );
}
