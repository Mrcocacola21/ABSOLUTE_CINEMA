import { useTranslation } from "react-i18next";

import { getGenreLabel, type GenreCode } from "@/shared/genres";
import type { MovieOption, ScheduleDayOption } from "@/shared/scheduleBrowse";

interface ScheduleBoardControlsProps {
  selectedDay: string;
  dayOptions: ScheduleDayOption[];
  movieId: string;
  genre: GenreCode | "";
  movies: MovieOption[];
  genres: GenreCode[];
  resultsLabel: string;
  onDayChange: (day: string) => void;
  onFilterChange: (key: "movieId" | "genre", value: string) => void;
  onReset: () => void;
}

export function ScheduleBoardControls({
  selectedDay,
  dayOptions,
  movieId,
  genre,
  movies,
  genres,
  resultsLabel,
  onDayChange,
  onFilterChange,
  onReset,
}: ScheduleBoardControlsProps) {
  const { t, i18n } = useTranslation();

  return (
    <section className="panel day-panel schedule-board-controls">
      <div className="toolbar-panel__header">
        <div>
          <p className="page-eyebrow">{t("chooseDay")}</p>
          <h2 className="section-title">{t("daySessionsTitle")}</h2>
          <p className="toolbar-panel__summary">{t("scheduleDayHint")}</p>
        </div>
        <p className="toolbar-panel__summary">{resultsLabel}</p>
      </div>

      <div className="toolbar toolbar--schedule-board">
        <label className="field">
          <span>{t("movie")}</span>
          <select value={movieId} onChange={(event) => onFilterChange("movieId", event.target.value)}>
            <option value="">{t("allMovies")}</option>
            {movies.map((movie) => (
              <option key={movie.id} value={movie.id}>
                {movie.title}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>{t("genre")}</span>
          <select value={genre} onChange={(event) => onFilterChange("genre", event.target.value)}>
            <option value="">{t("allGenres")}</option>
            {genres.map((currentGenre) => (
              <option key={currentGenre} value={currentGenre}>
                {getGenreLabel(currentGenre, i18n.language)}
              </option>
            ))}
          </select>
        </label>

        <div className="toolbar__actions">
          <button className="button--ghost" type="button" onClick={onReset}>
            {t("resetFilters")}
          </button>
        </div>
      </div>

      {dayOptions.length > 0 ? (
        <div className="day-pills">
          {dayOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`day-pill${option.value === selectedDay ? " is-active" : ""}`}
              onClick={() => onDayChange(option.value)}
            >
              <strong>{option.label}</strong>
              <span>{option.count}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="empty-state">{t("scheduleEmptyDays")}</div>
      )}
    </section>
  );
}
