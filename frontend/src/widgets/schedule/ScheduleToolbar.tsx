import { useTranslation } from "react-i18next";

interface MovieOption {
  id: string;
  title: string;
}

interface ScheduleToolbarProps {
  sortBy: string;
  sortOrder: string;
  movieId: string;
  movies: MovieOption[];
  onChange: (key: string, value: string) => void;
}

export function ScheduleToolbar({
  sortBy,
  sortOrder,
  movieId,
  movies,
  onChange,
}: ScheduleToolbarProps) {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <div className="toolbar">
        <label className="field">
          <span>{t("sortBy")}</span>
          <select value={sortBy} onChange={(event) => onChange("sortBy", event.target.value)}>
            <option value="movie_title">{t("movie")}</option>
            <option value="available_seats">{t("availableSeats")}</option>
            <option value="start_time">{t("dateTime")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("sortOrder")}</span>
          <select value={sortOrder} onChange={(event) => onChange("sortOrder", event.target.value)}>
            <option value="asc">{t("ascending")}</option>
            <option value="desc">{t("descending")}</option>
          </select>
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
      </div>
    </section>
  );
}
