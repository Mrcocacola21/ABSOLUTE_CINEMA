import { useState } from "react";

import type { MovieCreatePayload, MovieUpdatePayload, SessionCreatePayload } from "@/api/admin";
import type { Movie, SessionDetails } from "@/types/domain";

interface AdminScheduleManagementProps {
  movies: Movie[];
  sessions: SessionDetails[];
  onCreateMovie: (payload: MovieCreatePayload) => Promise<void>;
  onUpdateMovie: (movieId: string, payload: MovieUpdatePayload) => Promise<void>;
  onCreateSession: (payload: SessionCreatePayload) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
}

export function AdminScheduleManagement({
  movies,
  sessions,
  onCreateMovie,
  onUpdateMovie,
  onCreateSession,
  onCancelSession,
}: AdminScheduleManagementProps) {
  const [movieForm, setMovieForm] = useState<MovieCreatePayload>({
    title: "",
    description: "",
    duration_minutes: 120,
    genres: [],
    is_active: true,
  });
  const [genresInput, setGenresInput] = useState("");
  const [editingMovieId, setEditingMovieId] = useState<string | null>(null);
  const [sessionForm, setSessionForm] = useState<SessionCreatePayload>({
    movie_id: "",
    start_time: "",
    price: 200,
  });
  const [cancelSessionId, setCancelSessionId] = useState("");

  function resetMovieForm() {
    setMovieForm({
      title: "",
      description: "",
      duration_minutes: 120,
      genres: [],
      is_active: true,
    });
    setGenresInput("");
    setEditingMovieId(null);
  }

  return (
    <section className="split-grid">
      <form
        className="form-card"
        onSubmit={(event) => {
          event.preventDefault();
          const payload: MovieCreatePayload = {
            ...movieForm,
            genres: genresInput
              .split(",")
              .map((genre) => genre.trim())
              .filter(Boolean),
          };

          if (editingMovieId) {
            void onUpdateMovie(editingMovieId, payload as MovieUpdatePayload).then(() => {
              resetMovieForm();
            });
            return;
          }

          void onCreateMovie(payload).then(() => {
            resetMovieForm();
          });
        }}
      >
        <h3>{editingMovieId ? "Edit movie" : "Create movie"}</h3>
        <div className="form-grid">
          <label className="field">
            <span>Title</span>
            <input
              value={movieForm.title}
              onChange={(event) => setMovieForm((current) => ({ ...current, title: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              value={movieForm.description}
              onChange={(event) => setMovieForm((current) => ({ ...current, description: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>Duration</span>
            <input
              type="number"
              value={movieForm.duration_minutes}
              onChange={(event) =>
                setMovieForm((current) => ({
                  ...current,
                  duration_minutes: Number(event.target.value),
                }))
              }
            />
          </label>
          <label className="field">
            <span>Age rating</span>
            <input
              value={movieForm.age_rating ?? ""}
              onChange={(event) =>
                setMovieForm((current) => ({
                  ...current,
                  age_rating: event.target.value || undefined,
                }))
              }
            />
          </label>
          <label className="field">
            <span>Poster URL</span>
            <input
              value={movieForm.poster_url ?? ""}
              onChange={(event) =>
                setMovieForm((current) => ({
                  ...current,
                  poster_url: event.target.value || undefined,
                }))
              }
            />
          </label>
          <label className="field">
            <span>Genres</span>
            <input
              value={genresInput}
              onChange={(event) => setGenresInput(event.target.value)}
              placeholder="Drama, Comedy, Animation"
            />
          </label>
        </div>
        <button className="button" type="submit">
          {editingMovieId ? "Update movie" : "Save movie"}
        </button>
        {editingMovieId ? (
          <button className="button--ghost" type="button" onClick={resetMovieForm}>
            Clear form
          </button>
        ) : null}
      </form>

      <form
        className="form-card"
        onSubmit={(event) => {
          event.preventDefault();
          void onCreateSession(sessionForm);
        }}
      >
        <h3>Schedule on timeline</h3>
        <div className="form-grid">
          <label className="field">
            <span>Movie</span>
            <select
              value={sessionForm.movie_id}
              onChange={(event) =>
                setSessionForm((current) => ({ ...current, movie_id: event.target.value }))
              }
            >
              <option value="">Select movie</option>
              {movies
                .filter((movie) => movie.is_active)
                .map((movie) => (
                  <option key={movie.id} value={movie.id}>
                    {movie.title}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>Start time</span>
            <input
              type="datetime-local"
              value={sessionForm.start_time}
              onChange={(event) =>
                setSessionForm((current) => ({ ...current, start_time: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Price</span>
            <input
              type="number"
              value={sessionForm.price}
              onChange={(event) =>
                setSessionForm((current) => ({
                  ...current,
                  price: Number(event.target.value),
                }))
              }
            />
          </label>
        </div>
        <button className="button" type="submit">
          Save session
        </button>
        <p className="muted">
          This panel already follows the timeline idea: choose an existing movie and place it into a time slot.
        </p>
      </form>

      <section className="form-card">
        <h3>Movie board</h3>
        <div className="list">
          {movies.map((movie) => (
            <article key={movie.id} className="card">
              <strong>{movie.title}</strong>
              <p className="muted">{movie.duration_minutes} min</p>
              <div className="stats-row">
                <span className="badge">{movie.is_active ? "active" : "inactive"}</span>
                {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
              </div>
              <button
                className="button--ghost"
                type="button"
                onClick={() => {
                  setEditingMovieId(movie.id);
                  setMovieForm({
                    title: movie.title,
                    description: movie.description,
                    duration_minutes: movie.duration_minutes,
                    poster_url: movie.poster_url ?? undefined,
                    age_rating: movie.age_rating ?? undefined,
                    genres: movie.genres,
                    is_active: movie.is_active,
                  });
                  setGenresInput(movie.genres.join(", "));
                }}
              >
                Edit movie
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="form-card">
        <h3>Schedule board</h3>
        <div className="list">
          {sessions.map((session) => (
            <article key={session.id} className="card">
              <strong>{session.movie.title}</strong>
              <p className="muted">
                {new Date(session.start_time).toLocaleString()} - {new Date(session.end_time).toLocaleTimeString()}
              </p>
              <div className="stats-row">
                <span className="badge">{session.price}</span>
                <span className="badge">{session.available_seats}/{session.total_seats}</span>
                <span className="badge">{session.status}</span>
              </div>
              {session.status === "scheduled" ? (
                <button
                  className="button--danger"
                  type="button"
                  onClick={() => {
                    setCancelSessionId(session.id);
                    void onCancelSession(session.id);
                  }}
                >
                  Cancel session
                </button>
              ) : null}
            </article>
          ))}
        </div>
        {cancelSessionId ? <p className="muted">Last cancellation request: {cancelSessionId}</p> : null}
      </section>
    </section>
  );
}
