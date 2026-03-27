import { formatCurrency, formatDateTime, formatStateLabel, formatTime } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, SessionDetails } from "@/types/domain";
import type { InspectorView, SessionDraft, SessionEditDraft } from "@/widgets/admin/chronoboard/types";
import { formatLocalDateTime, getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

interface ChronoboardInspectorProps {
  inspectorView: InspectorView;
  draftPlacement: SessionDraft | null;
  editingDraft: SessionEditDraft | null;
  selectedSession: SessionDetails | null;
  draftMovie: Movie | null;
  editingMovie: Movie | null;
  movieOptionsForSessionForms: Movie[];
  isBusy: boolean;
  busyActionLabel?: string;
  onDiscardDraft: () => void;
  onUpdateDraftField: <K extends keyof SessionDraft>(field: K, value: SessionDraft[K]) => void;
  onUpdateEditingDraftField: <K extends keyof SessionEditDraft>(field: K, value: SessionEditDraft[K]) => void;
  onResetDraftEndTime: () => void;
  onCreateDraftSession: () => Promise<void> | void;
  onUpdateEditedSession: () => Promise<void> | void;
  onBackToSession: () => void;
  onOpenEditSessionDraft: (session: SessionDetails) => void;
  onCancelSelectedSession: () => Promise<void> | void;
  onDeleteSelectedSession: () => Promise<void> | void;
  onJumpToToday: () => void;
}

export function ChronoboardInspector({
  inspectorView,
  draftPlacement,
  editingDraft,
  selectedSession,
  draftMovie,
  editingMovie,
  movieOptionsForSessionForms,
  isBusy,
  busyActionLabel,
  onDiscardDraft,
  onUpdateDraftField,
  onUpdateEditingDraftField,
  onResetDraftEndTime,
  onCreateDraftSession,
  onUpdateEditedSession,
  onBackToSession,
  onOpenEditSessionDraft,
  onCancelSelectedSession,
  onDeleteSelectedSession,
  onJumpToToday,
}: ChronoboardInspectorProps) {
  return (
    <section className="card inspector-panel">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">Inspector</p>
          <h3 className="section-title">
            {inspectorView === "draft"
              ? "Pending draft"
              : inspectorView === "edit"
                ? "Edit session"
                : inspectorView === "session"
                  ? "Confirmed session"
                  : "Control center"}
          </h3>
          <p className="muted">
            {inspectorView === "draft"
              ? "Review the draft, adjust the fields, and explicitly confirm it."
              : inspectorView === "session"
                ? "Inspect the saved session and manage it here."
                : inspectorView === "edit"
                  ? "Update the selected session without leaving the board."
                  : "Select a draft or a session on the board to inspect it."}
          </p>
        </div>
        {draftPlacement && inspectorView === "draft" ? (
          <button className="button--ghost" type="button" onClick={onDiscardDraft}>
            Discard draft
          </button>
        ) : null}
      </div>

      {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

      {inspectorView === "draft" && draftPlacement ? (
        <form
          className="admin-planner__form"
          onSubmit={(event) => {
            event.preventDefault();
            void onCreateDraftSession();
          }}
        >
          <p className="muted">{draftPlacement.sourceLabel}</p>
          <div className="form-grid">
            <label className="field field--wide">
              <span>Movie</span>
              <select
                required
                disabled={isBusy}
                value={draftPlacement.movie_id}
                onChange={(event) => onUpdateDraftField("movie_id", event.target.value)}
              >
                <option value="">Select a movie</option>
                {movieOptionsForSessionForms.map((movie) => (
                  <option key={movie.id} value={movie.id}>
                    {movie.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Planned start</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={draftPlacement.start_time}
                onChange={(event) => onUpdateDraftField("start_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Calculated end</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={draftPlacement.end_time}
                onChange={(event) => onUpdateDraftField("end_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Price</span>
              <input
                required
                min={0}
                type="number"
                disabled={isBusy}
                value={draftPlacement.price}
                onChange={(event) => onUpdateDraftField("price", Number(event.target.value))}
              />
            </label>
          </div>

          {draftMovie ? (
            <div className="inspector-panel__summary">
              <span className="badge">Draft</span>
              <span className="badge">{draftMovie.duration_minutes} min</span>
              {draftMovie.age_rating ? <span className="badge">{draftMovie.age_rating}</span> : null}
              <span className="badge">{formatLocalDateTime(draftPlacement.start_time)}</span>
            </div>
          ) : null}

          {!draftPlacement.autoFillEndTime && draftMovie ? (
            <button className="button--ghost" type="button" disabled={isBusy} onClick={onResetDraftEndTime}>
              Reset to the recommended end time
            </button>
          ) : null}

          <div className="actions-row">
            <button className="button" type="submit" disabled={isBusy}>
              Create Session
            </button>
          </div>
        </form>
      ) : null}

      {inspectorView === "edit" && editingDraft ? (
        <form
          className="admin-planner__form"
          onSubmit={(event) => {
            event.preventDefault();
            void onUpdateEditedSession();
          }}
        >
          <p className="muted">{editingDraft.sourceLabel}</p>
          <div className="form-grid">
            <label className="field field--wide">
              <span>Movie</span>
              <select
                required
                disabled={isBusy}
                value={editingDraft.movie_id}
                onChange={(event) => onUpdateEditingDraftField("movie_id", event.target.value)}
              >
                <option value="">Select a movie</option>
                {movieOptionsForSessionForms.map((movie) => (
                  <option key={movie.id} value={movie.id}>
                    {movie.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Starts at</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={editingDraft.start_time}
                onChange={(event) => onUpdateEditingDraftField("start_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Ends at</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={editingDraft.end_time}
                onChange={(event) => onUpdateEditingDraftField("end_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Price</span>
              <input
                required
                min={0}
                type="number"
                disabled={isBusy}
                value={editingDraft.price}
                onChange={(event) => onUpdateEditingDraftField("price", Number(event.target.value))}
              />
            </label>
          </div>

          {editingMovie ? (
            <div className="inspector-panel__summary">
              <span className="badge">Editing saved session</span>
              <span className="badge">{editingMovie.duration_minutes} min</span>
              <span className="badge">{formatLocalDateTime(editingDraft.start_time)}</span>
            </div>
          ) : null}

          <div className="actions-row">
            <button className="button" type="submit" disabled={isBusy}>
              Save session changes
            </button>
            <button className="button--ghost" type="button" disabled={isBusy} onClick={onBackToSession}>
              Back to session
            </button>
          </div>
        </form>
      ) : null}

      {inspectorView === "session" && selectedSession ? (
        <div className="inspector-panel__details">
          <div className="inspector-panel__poster-row">
            <div className="media-tile inspector-panel__poster" aria-hidden="true">
              {selectedSession.movie.poster_url ? (
                <img src={selectedSession.movie.poster_url} alt="" className="media-tile__image" />
              ) : (
                <span>{getMovieMonogram(selectedSession.movie.title)}</span>
              )}
            </div>
            <div>
              <strong>{selectedSession.movie.title}</strong>
              <p className="muted">
                {formatDateTime(selectedSession.start_time)} to {formatTime(selectedSession.end_time)}
              </p>
            </div>
          </div>

          <div className="stats-row">
            <span className="badge">{formatStateLabel(selectedSession.status)}</span>
            <span className="badge">{formatCurrency(selectedSession.price)}</span>
            <span className="badge">{selectedSession.total_seats - selectedSession.available_seats} sold</span>
            <span className="badge">
              {selectedSession.available_seats}/{selectedSession.total_seats} left
            </span>
          </div>

          <p className="muted">{selectedSession.movie.description}</p>

          <div className="stats-row">
            {selectedSession.movie.age_rating ? <span className="badge">{selectedSession.movie.age_rating}</span> : null}
            {selectedSession.movie.genres.length > 0 ? (
              <span className="badge">{selectedSession.movie.genres.join(", ")}</span>
            ) : null}
          </div>

          <div className="actions-row">
            <button
              className="button--ghost"
              type="button"
              disabled={isBusy}
              onClick={() => onOpenEditSessionDraft(selectedSession)}
            >
              Edit session
            </button>
            <button
              className="button--ghost"
              type="button"
              disabled={isBusy || selectedSession.status !== "scheduled"}
              onClick={() => void onCancelSelectedSession()}
            >
              Cancel session
            </button>
            <button
              className="button--danger"
              type="button"
              disabled={isBusy}
              onClick={() => void onDeleteSelectedSession()}
            >
              Delete session
            </button>
          </div>
        </div>
      ) : null}

      {inspectorView === "none" ? (
        <StatePanel
          title="Use the inspector as the control center"
          message="Drag a movie from the Planning Shelf onto the board to stage a gray draft, or select an existing session card to inspect it."
          action={
            <button className="button--ghost" type="button" onClick={onJumpToToday}>
              Jump to today
            </button>
          }
        />
      ) : null}
    </section>
  );
}
