import { useTranslation } from "react-i18next";

interface MovieOption {
  id: string;
  title: string;
}

interface ScheduleToolbarProps {
  query: string;
  sortBy: string;
  sortOrder: string;
  movieId: string;
  movies: MovieOption[];
  resultsLabel: string;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
}

export function ScheduleToolbar({
  query,
  sortBy,
  sortOrder,
  movieId,
  movies,
  resultsLabel,
  onChange,
  onReset,
}: ScheduleToolbarProps) {
  const { t } = useTranslation();

  return (
    <section className="panel toolbar-panel">
      <div className="toolbar-panel__header">
        <div>
          <p className="page-eyebrow">{t("filters")}</p>
          <h2 className="section-title">{t("browseControls")}</h2>
        </div>
        <p className="toolbar-panel__summary">{resultsLabel}</p>
      </div>

      <div className="toolbar">
        <label className="field field--search">
          <span>{t("searchByTitle")}</span>
          <input
            value={query}
            onChange={(event) => onChange("query", event.target.value)}
            placeholder={t("searchPlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("movie")}</span>
          <select value={movieId} onChange={(event) => onChange("movieId", event.target.value)}>
            <option value="">{t("allMovies")}</option>
            {movies.map((movie) => (
              <option key={movie.id} value={movie.id}>
                {movie.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("sortBy")}</span>
          <select value={sortBy} onChange={(event) => onChange("sortBy", event.target.value)}>
            <option value="start_time">{t("dateTime")}</option>
            <option value="available_seats">{t("availableSeats")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("sortOrder")}</span>
          <select value={sortOrder} onChange={(event) => onChange("sortOrder", event.target.value)}>
            <option value="asc">{t("ascending")}</option>
            <option value="desc">{t("descending")}</option>
          </select>
        </label>
        <div className="toolbar__actions">
          <button className="button--ghost" type="button" onClick={onReset}>
            {t("resetFilters")}
          </button>
        </div>
      </div>
    </section>
  );
}
