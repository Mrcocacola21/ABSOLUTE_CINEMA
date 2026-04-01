import type { DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { getGenreLabels } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import { getMovieStatusBadgeClassName } from "@/shared/movieStatus";
import { formatStateLabel } from "@/shared/presentation";
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
  const { i18n } = useTranslation();

  return (
    <section className="card planning-shelf">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">Planning Shelf</p>
          <h3 className="section-title">Drag source / staging area</h3>
          <p className="muted">Pick a planned or active title, then drag it onto the board to create a gray draft.</p>
        </div>
        <span className="badge">{planningMovies.length}</span>
      </div>

      <label className="field">
        <span>Find a schedule-ready movie</span>
        <input
          value={plannerMovieQuery}
          onChange={(event) => onPlannerMovieQueryChange(event.target.value)}
          placeholder="Search planned and active titles"
        />
      </label>

      {selectedMovie ? (
        <StatusBanner
          tone="info"
          title="Selected movie"
          message={`${getLocalizedText(selectedMovie.title, i18n.language)} is queued for board placement. Drag it or click a free slot on the timeline.`}
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
          const movieTitle = getLocalizedText(movie.title, i18n.language);

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
                    <span>{getMovieMonogram(movieTitle)}</span>
                  )}
                </div>
                <div className="admin-source-card__copy">
                  <strong className="admin-source-card__title">{movieTitle}</strong>
                  <div className="admin-source-card__meta">
                    <span className={getMovieStatusBadgeClassName(movie.status)}>
                      {formatStateLabel(movie.status)}
                    </span>
                    {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                    <span className="badge admin-source-card__duration-badge">{movie.duration_minutes} min</span>
                  </div>
                  {movie.genres.length > 0 ? (
                    <div className="admin-source-card__genres">
                      <span className="badge admin-source-card__genres-badge">
                        {getGenreLabels(movie.genres, i18n.language).join(", ")}
                      </span>
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="actions-row admin-source-card__actions">
                <button
                  className="button--ghost"
                  type="button"
                  disabled={isBusy}
                  onClick={() => onSelectMovie(movie)}
                >
                  Select
                </button>
              </div>
            </article>
          );
        })}

        {planningMovies.length === 0 ? (
          <section className="empty-state empty-state--panel">
            <h2>No schedule-ready movies</h2>
            <p>Create a planned movie or return a deactivated one to planned before placing it on the board.</p>
          </section>
        ) : null}
      </div>
    </section>
  );
}
