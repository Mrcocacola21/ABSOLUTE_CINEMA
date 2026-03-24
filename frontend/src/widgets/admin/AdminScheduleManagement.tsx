import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  MovieCreatePayload,
  MovieUpdatePayload,
  SessionCreatePayload,
  SessionUpdatePayload,
} from "@/api/admin";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import type { Movie, SessionDetails, TicketListItem, User } from "@/types/domain";

interface AdminScheduleManagementProps {
  movies: Movie[];
  sessions: SessionDetails[];
  tickets: TicketListItem[];
  users: User[];
  isBusy: boolean;
  busyActionLabel?: string;
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

export function AdminScheduleManagement({
  movies,
  sessions,
  tickets,
  users,
  isBusy,
  busyActionLabel,
  onCreateMovie,
  onUpdateMovie,
  onDeactivateMovie,
  onDeleteMovie,
  onCreateSession,
  onUpdateSession,
  onCancelSession,
  onDeleteSession,
}: AdminScheduleManagementProps) {
  const { t } = useTranslation();
  const [movieForm, setMovieForm] = useState<MovieCreatePayload>(emptyMovieForm);
  const [genresInput, setGenresInput] = useState("");
  const [editingMovieId, setEditingMovieId] = useState<string | null>(null);
  const [sessionForm, setSessionForm] = useState<SessionCreatePayload>(emptySessionForm);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);

  const sortedMovies = useMemo(
    () => [...movies].sort((left, right) => left.title.localeCompare(right.title)),
    [movies],
  );
  const sortedSessions = useMemo(
    () =>
      [...sessions].sort(
        (left, right) =>
          new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
      ),
    [sessions],
  );
  const sortedTickets = useMemo(
    () =>
      [...tickets].sort(
        (left, right) =>
          new Date(right.purchased_at).getTime() - new Date(left.purchased_at).getTime(),
      ),
    [tickets],
  );
  const sortedUsers = useMemo(
    () =>
      [...users].sort(
        (left, right) =>
          new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
      ),
    [users],
  );
  const selectableMovies = useMemo(
    () => sortedMovies.filter((movie) => movie.is_active || movie.id === sessionForm.movie_id),
    [sessionForm.movie_id, sortedMovies],
  );
  const movieSubmitLabel = editingMovieId ? "Save movie changes" : "Create movie";
  const sessionSubmitLabel = editingSessionId ? "Save session changes" : "Create session";

  function resetMovieForm() {
    setMovieForm(emptyMovieForm);
    setGenresInput("");
    setEditingMovieId(null);
  }

  function resetSessionForm() {
    setSessionForm(emptySessionForm);
    setEditingSessionId(null);
  }

  async function handleMovieSubmit() {
    const payload: MovieCreatePayload = {
      ...movieForm,
      genres: genresInput
        .split(",")
        .map((genre) => genre.trim())
        .filter(Boolean),
    };

    if (editingMovieId) {
      await onUpdateMovie(editingMovieId, payload as MovieUpdatePayload);
      resetMovieForm();
      return;
    }

    await onCreateMovie(payload);
    resetMovieForm();
  }

  async function handleSessionSubmit() {
    if (editingSessionId) {
      await onUpdateSession(editingSessionId, sessionForm);
      resetSessionForm();
      return;
    }

    await onCreateSession(sessionForm);
    resetSessionForm();
  }

  return (
    <section className="admin-stack">
      <section className="admin-builder">
        <form
          className="form-card admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleMovieSubmit();
          }}
        >
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">{t("adminStepOne")}</p>
              <h2 className="section-title">
                {editingMovieId ? t("movieFormEditTitle") : t("movieFormNewTitle")}
              </h2>
            </div>
            {editingMovieId ? (
              <button className="button--ghost" type="button" disabled={isBusy} onClick={resetMovieForm}>
                {t("clearForm")}
              </button>
            ) : null}
          </div>
          {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

          <div className="form-grid">
            <label className="field">
              <span>{t("movie")}</span>
              <input
                required
                disabled={isBusy}
                value={movieForm.title}
                onChange={(event) =>
                  setMovieForm((current) => ({ ...current, title: event.target.value }))
                }
              />
            </label>
            <label className="field field--wide">
              <span>{t("descriptionLabel")}</span>
              <textarea
                required
                disabled={isBusy}
                value={movieForm.description}
                onChange={(event) =>
                  setMovieForm((current) => ({ ...current, description: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>{t("durationMinutes")}</span>
              <input
                min={1}
                max={600}
                required
                type="number"
                disabled={isBusy}
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
              <span>{t("ageRating")}</span>
              <input
                disabled={isBusy}
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
              <span>{t("posterUrl")}</span>
              <input
                type="url"
                disabled={isBusy}
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
              <span>{t("genresLabel")}</span>
              <input
                disabled={isBusy}
                value={genresInput}
                onChange={(event) => setGenresInput(event.target.value)}
                placeholder={t("genresPlaceholder")}
              />
            </label>
            <label className="field field--checkbox">
              <input
                checked={movieForm.is_active}
                type="checkbox"
                disabled={isBusy}
                onChange={(event) =>
                  setMovieForm((current) => ({
                    ...current,
                    is_active: event.target.checked,
                  }))
                }
              />
              <span>{t("movieActiveLabel")}</span>
            </label>
          </div>

          <div className="actions-row">
            <button className="button" type="submit" disabled={isBusy}>
              {isBusy ? "Saving..." : movieSubmitLabel}
            </button>
          </div>
          <p className="muted">{t("movieFormHint")}</p>
        </form>

        <form
          className="form-card admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSessionSubmit();
          }}
        >
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">{t("adminStepTwo")}</p>
              <h2 className="section-title">
                {editingSessionId ? t("sessionFormEditTitle") : t("sessionFormNewTitle")}
              </h2>
            </div>
            {editingSessionId ? (
              <button className="button--ghost" type="button" disabled={isBusy} onClick={resetSessionForm}>
                {t("clearForm")}
              </button>
            ) : null}
          </div>
          {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

          <div className="form-grid">
            <label className="field">
              <span>{t("movie")}</span>
              <select
                required
                disabled={isBusy}
                value={sessionForm.movie_id}
                onChange={(event) =>
                  setSessionForm((current) => ({ ...current, movie_id: event.target.value }))
                }
              >
                <option value="">{t("selectMoviePlaceholder")}</option>
                {selectableMovies.map((movie) => (
                  <option key={movie.id} value={movie.id}>
                    {movie.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("startsAt")}</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={sessionForm.start_time}
                onChange={(event) =>
                  setSessionForm((current) => ({ ...current, start_time: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>{t("endsAt")}</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={sessionForm.end_time}
                onChange={(event) =>
                  setSessionForm((current) => ({ ...current, end_time: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>{t("price")}</span>
              <input
                min={0}
                required
                type="number"
                disabled={isBusy}
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
            <button className="button" type="submit" disabled={isBusy}>
              {isBusy ? "Saving..." : sessionSubmitLabel}
            </button>
          </div>
          <p className="muted">{t("sessionFormHint")}</p>
        </form>
      </section>

      <section className="admin-collections">
        <section className="form-card admin-section">
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">{t("adminLibraryEyebrow")}</p>
              <h2 className="section-title">{t("movieCatalogTitle")}</h2>
            </div>
            <span className="badge">{sortedMovies.length}</span>
          </div>

          <div className="list">
            {sortedMovies.map((movie) => (
              <article key={movie.id} className="card admin-card">
                <div className="admin-card__header">
                  <div>
                    <strong>{movie.title}</strong>
                    <p className="muted">{movie.description}</p>
                  </div>
                  <div className="stats-row">
                    <span className="badge">{movie.duration_minutes} min</span>
                    <span className="badge">
                      {movie.is_active ? t("activeLabel") : t("inactiveLabel")}
                    </span>
                  </div>
                </div>
                <div className="stats-row">
                  {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                  {movie.genres.length ? <span className="badge">{movie.genres.join(", ")}</span> : null}
                </div>
                <div className="actions-row">
                  <button
                    className="button--ghost"
                    type="button"
                    disabled={isBusy}
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
                  <button
                    className="button--ghost"
                    disabled={!movie.is_active || isBusy}
                    type="button"
                    onClick={() => {
                      if (window.confirm(`Deactivate "${movie.title}"? Existing history will be preserved.`)) {
                        void onDeactivateMovie(movie.id);
                      }
                    }}
                  >
                    Deactivate
                  </button>
                  <button
                    className="button--danger"
                    type="button"
                    disabled={isBusy}
                    onClick={() => {
                      if (window.confirm(`Delete "${movie.title}"? This only works when no sessions reference it.`)) {
                        void onDeleteMovie(movie.id);
                      }
                    }}
                  >
                    Delete movie
                  </button>
                </div>
              </article>
            ))}
            {sortedMovies.length === 0 ? (
              <section className="empty-state empty-state--panel">
                <h2>No movies yet</h2>
                <p>Create the first movie to start building the cinema schedule.</p>
              </section>
            ) : null}
          </div>
        </section>

        <section className="form-card admin-section">
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">{t("adminSessionsEyebrow")}</p>
              <h2 className="section-title">{t("sessionBoardTitle")}</h2>
            </div>
            <span className="badge">{sortedSessions.length}</span>
          </div>

          <div className="list">
            {sortedSessions.map((session) => (
              <article key={session.id} className="card admin-card">
                <div className="admin-card__header">
                  <div>
                    <strong>{session.movie.title}</strong>
                    <p className="muted">
                      {formatDateTime(session.start_time)} | {formatDateTime(session.end_time)}
                    </p>
                  </div>
                  <div className="stats-row">
                    <span className="badge">{formatCurrency(session.price)}</span>
                    <span className="badge">
                      {session.available_seats}/{session.total_seats}
                    </span>
                    <span className="badge">{formatStateLabel(session.status)}</span>
                  </div>
                </div>
                <div className="actions-row">
                  <button
                    className="button--ghost"
                    type="button"
                    disabled={isBusy}
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
                    Edit session
                  </button>
                  <button
                    className="button--ghost"
                    disabled={session.status !== "scheduled" || isBusy}
                    type="button"
                    onClick={() => {
                      if (window.confirm(`Cancel the session for "${session.movie.title}"?`)) {
                        void onCancelSession(session.id);
                      }
                    }}
                  >
                    Cancel session
                  </button>
                  <button
                    className="button--danger"
                    type="button"
                    disabled={isBusy}
                    onClick={() => {
                      if (window.confirm(`Delete the session for "${session.movie.title}"?`)) {
                        void onDeleteSession(session.id);
                      }
                    }}
                  >
                    Delete session
                  </button>
                </div>
              </article>
            ))}
            {sortedSessions.length === 0 ? (
              <section className="empty-state empty-state--panel">
                <h2>No sessions yet</h2>
                <p>Create a movie first, then add the first session slot.</p>
              </section>
            ) : null}
          </div>
        </section>
      </section>

      <section className="cards-grid admin-secondary-grid">
        <section className="form-card admin-section">
          <div className="admin-section__header">
            <h2 className="section-title">{t("ticketsPanelTitle")}</h2>
            <span className="badge">{sortedTickets.length}</span>
          </div>
          <div className="list">
            {sortedTickets.map((ticket) => (
              <article key={ticket.id} className="card admin-card">
                <strong>{ticket.movie_title}</strong>
                <p className="muted">
                  {formatDateTime(ticket.session_start_time)} | {t("seatLabel")} {ticket.seat_row}-{ticket.seat_number}
                </p>
                <div className="stats-row">
                  <span className="badge">{formatStateLabel(ticket.status)}</span>
                  <span className="badge">{formatStateLabel(ticket.session_status)}</span>
                  <span className="badge">{formatCurrency(ticket.price)}</span>
                  {ticket.user_name ? <span className="badge">{ticket.user_name}</span> : null}
                </div>
              </article>
            ))}
            {sortedTickets.length === 0 ? (
              <section className="empty-state empty-state--panel">
                <h2>No tickets yet</h2>
                <p>Ticket purchases will appear here once customers start booking seats.</p>
              </section>
            ) : null}
          </div>
        </section>

        <section className="form-card admin-section">
          <div className="admin-section__header">
            <h2 className="section-title">{t("usersPanelTitle")}</h2>
            <span className="badge">{sortedUsers.length}</span>
          </div>
          <div className="list">
            {sortedUsers.map((user) => (
              <article key={user.id} className="card admin-card">
                <strong>{user.name}</strong>
                <p className="muted">{user.email}</p>
                <div className="stats-row">
                  <span className="badge">{formatStateLabel(user.role)}</span>
                  <span className="badge">
                    {user.is_active ? t("activeLabel") : t("inactiveLabel")}
                  </span>
                  <span className="badge">{formatDateTime(user.created_at)}</span>
                </div>
              </article>
            ))}
            {sortedUsers.length === 0 ? (
              <section className="empty-state empty-state--panel">
                <h2>No users yet</h2>
                <p>Registered users will appear here after they create accounts.</p>
              </section>
            ) : null}
          </div>
        </section>
      </section>
    </section>
  );
}
