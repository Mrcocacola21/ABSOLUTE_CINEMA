import { useState } from "react";

import type {
  MovieCreatePayload,
  MovieUpdatePayload,
  SessionCreatePayload,
  SessionUpdatePayload,
} from "@/api/admin";
import type { Movie, SessionDetails, TicketListItem, User } from "@/types/domain";

interface AdminScheduleManagementProps {
  movies: Movie[];
  sessions: SessionDetails[];
  tickets: TicketListItem[];
  users: User[];
  onCreateMovie: (payload: MovieCreatePayload) => Promise<void>;
  onUpdateMovie: (movieId: string, payload: MovieUpdatePayload) => Promise<void>;
  onDeactivateMovie: (movieId: string) => Promise<void>;
  onDeleteMovie: (movieId: string) => Promise<void>;
  onCreateSession: (payload: SessionCreatePayload) => Promise<void>;
  onUpdateSession: (sessionId: string, payload: SessionUpdatePayload) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
}

const emptyMovieForm: MovieCreatePayload = {
  title: "",
  description: "",
  duration_minutes: 120,
  genres: [],
  is_active: true,
};

const emptySessionForm: SessionCreatePayload = {
  movie_id: "",
  start_time: "",
  end_time: "",
  price: 200,
};

function toDateTimeLocal(value: string): string {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "UAH",
    maximumFractionDigits: 0,
  }).format(value);
}

export function AdminScheduleManagement({
  movies,
  sessions,
  tickets,
  users,
  onCreateMovie,
  onUpdateMovie,
  onDeactivateMovie,
  onDeleteMovie,
  onCreateSession,
  onUpdateSession,
  onCancelSession,
  onDeleteSession,
}: AdminScheduleManagementProps) {
  const [movieForm, setMovieForm] = useState<MovieCreatePayload>(emptyMovieForm);
  const [genresInput, setGenresInput] = useState("");
  const [editingMovieId, setEditingMovieId] = useState<string | null>(null);
  const [sessionForm, setSessionForm] = useState<SessionCreatePayload>(emptySessionForm);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);

  function resetMovieForm() {
    setMovieForm(emptyMovieForm);
    setGenresInput("");
    setEditingMovieId(null);
  }

  function resetSessionForm() {
    setSessionForm(emptySessionForm);
    setEditingSessionId(null);
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
              required
              value={movieForm.title}
              onChange={(event) => setMovieForm((current) => ({ ...current, title: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              required
              value={movieForm.description}
              onChange={(event) => setMovieForm((current) => ({ ...current, description: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>Duration in minutes</span>
            <input
              min={1}
              max={600}
              required
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
              type="url"
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
          <label className="field field--checkbox">
            <input
              checked={movieForm.is_active}
              type="checkbox"
              onChange={(event) =>
                setMovieForm((current) => ({
                  ...current,
                  is_active: event.target.checked,
                }))
              }
            />
            <span>Movie is active</span>
          </label>
        </div>
        <div className="actions-row">
          <button className="button" type="submit">
            {editingMovieId ? "Update movie" : "Save movie"}
          </button>
          {editingMovieId ? (
            <button className="button--ghost" type="button" onClick={resetMovieForm}>
              Clear form
            </button>
          ) : null}
        </div>
        <p className="muted">
          Deactivation keeps the movie record for existing sessions. Deletion is available only if the movie was never
          scheduled.
        </p>
      </form>

      <form
        className="form-card"
        onSubmit={(event) => {
          event.preventDefault();
          if (editingSessionId) {
            void onUpdateSession(editingSessionId, sessionForm).then(() => {
              resetSessionForm();
            });
            return;
          }

          void onCreateSession(sessionForm).then(() => {
            resetSessionForm();
          });
        }}
      >
        <h3>{editingSessionId ? "Edit session" : "Schedule a session"}</h3>
        <div className="form-grid">
          <label className="field">
            <span>Movie</span>
            <select
              required
              value={sessionForm.movie_id}
              onChange={(event) =>
                setSessionForm((current) => ({ ...current, movie_id: event.target.value }))
              }
            >
              <option value="">Select movie</option>
              {movies
                .filter((movie) => movie.is_active || movie.id === sessionForm.movie_id)
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
              required
              type="datetime-local"
              value={sessionForm.start_time}
              onChange={(event) =>
                setSessionForm((current) => ({ ...current, start_time: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>End time</span>
            <input
              required
              type="datetime-local"
              value={sessionForm.end_time}
              onChange={(event) =>
                setSessionForm((current) => ({ ...current, end_time: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Price</span>
            <input
              min={0}
              required
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
        <div className="actions-row">
          <button className="button" type="submit">
            {editingSessionId ? "Update session" : "Save session"}
          </button>
          {editingSessionId ? (
            <button className="button--ghost" type="button" onClick={resetSessionForm}>
              Clear form
            </button>
          ) : null}
        </div>
        <p className="muted">
          Sessions are validated against the one-hall rule, the 09:00-22:00 start window, and the selected movie
          duration.
        </p>
      </form>

      <section className="form-card">
        <h3>Movie board</h3>
        <div className="list">
          {movies.map((movie) => (
            <article key={movie.id} className="card">
              <strong>{movie.title}</strong>
              <p className="muted">{movie.description}</p>
              <div className="stats-row">
                <span className="badge">{movie.duration_minutes} min</span>
                <span className="badge">{movie.is_active ? "active" : "inactive"}</span>
                {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                {movie.genres.length ? <span className="badge">{movie.genres.join(", ")}</span> : null}
              </div>
              <div className="actions-row">
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
                  Edit
                </button>
                <button
                  className="button--ghost"
                  disabled={!movie.is_active}
                  type="button"
                  onClick={() => {
                    void onDeactivateMovie(movie.id);
                  }}
                >
                  Deactivate
                </button>
                <button
                  className="button--danger"
                  type="button"
                  onClick={() => {
                    void onDeleteMovie(movie.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
          {movies.length === 0 ? <p className="empty-state">No movies yet.</p> : null}
        </div>
      </section>

      <section className="form-card">
        <h3>Schedule board</h3>
        <div className="list">
          {sessions.map((session) => (
            <article key={session.id} className="card">
              <strong>{session.movie.title}</strong>
              <p className="muted">
                {new Date(session.start_time).toLocaleString()} - {new Date(session.end_time).toLocaleString()}
              </p>
              <div className="stats-row">
                <span className="badge">{formatCurrency(session.price)}</span>
                <span className="badge">
                  {session.available_seats}/{session.total_seats}
                </span>
                <span className="badge">{session.status}</span>
              </div>
              <div className="actions-row">
                <button
                  className="button--ghost"
                  type="button"
                  onClick={() => {
                    setEditingSessionId(session.id);
                    setSessionForm({
                      movie_id: session.movie_id,
                      start_time: toDateTimeLocal(session.start_time),
                      end_time: toDateTimeLocal(session.end_time),
                      price: session.price,
                    });
                  }}
                >
                  Edit
                </button>
                <button
                  className="button--ghost"
                  disabled={session.status !== "scheduled"}
                  type="button"
                  onClick={() => {
                    void onCancelSession(session.id);
                  }}
                >
                  Cancel
                </button>
                <button
                  className="button--danger"
                  type="button"
                  onClick={() => {
                    void onDeleteSession(session.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
          {sessions.length === 0 ? <p className="empty-state">No sessions yet.</p> : null}
        </div>
      </section>

      <section className="form-card">
        <h3>Tickets</h3>
        <div className="list">
          {tickets.map((ticket) => (
            <article key={ticket.id} className="card">
              <strong>{ticket.movie_title}</strong>
              <p className="muted">
                {new Date(ticket.session_start_time).toLocaleString()} | seat {ticket.seat_row}-{ticket.seat_number}
              </p>
              <div className="stats-row">
                <span className="badge">{ticket.status}</span>
                <span className="badge">{ticket.session_status}</span>
                <span className="badge">{formatCurrency(ticket.price)}</span>
                {ticket.user_name ? <span className="badge">{ticket.user_name}</span> : null}
                {ticket.user_email ? <span className="badge">{ticket.user_email}</span> : null}
              </div>
            </article>
          ))}
          {tickets.length === 0 ? <p className="empty-state">No tickets found.</p> : null}
        </div>
      </section>

      <section className="form-card">
        <h3>Users</h3>
        <div className="list">
          {users.map((user) => (
            <article key={user.id} className="card">
              <strong>{user.name}</strong>
              <p className="muted">{user.email}</p>
              <div className="stats-row">
                <span className="badge">{user.role}</span>
                <span className="badge">{user.is_active ? "active" : "inactive"}</span>
                <span className="badge">{new Date(user.created_at).toLocaleDateString()}</span>
              </div>
            </article>
          ))}
          {users.length === 0 ? <p className="empty-state">No users found.</p> : null}
        </div>
      </section>
    </section>
  );
}
