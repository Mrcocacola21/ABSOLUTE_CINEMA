import { useTranslation } from "react-i18next";

import { getGenreLabels } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatDateTime, formatStateLabel, formatTime } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, SessionDetails } from "@/types/domain";
import type {
  DraftCalendarDay,
  DraftDatePlan,
  InspectorView,
  SessionDraft,
  SessionEditDraft,
} from "@/widgets/admin/chronoboard/types";
import { formatLocalDateTime, getMovieMonogram } from "@/widgets/admin/chronoboard/utils";

interface ChronoboardInspectorProps {
  inspectorView: InspectorView;
  draftPlacement: SessionDraft | null;
  draftDatePlans: DraftDatePlan[];
  draftSelectionSummary: {
    selectedCount: number;
    readyCount: number;
    conflictCount: number;
  };
  draftWeekdayLabels: string[];
  draftCalendarMonthLabel: string;
  draftCalendarDays: DraftCalendarDay[];
  editingDraft: SessionEditDraft | null;
  selectedSession: SessionDetails | null;
  draftMovie: Movie | null;
  editingMovie: Movie | null;
  movieOptionsForSessionForms: Movie[];
  isBusy: boolean;
  busyActionLabel?: string;
  onDiscardDraft: () => void;
  onToggleDraftDate: (dateKey: string) => void;
  onShowPreviousDraftMonth: () => void;
  onShowNextDraftMonth: () => void;
  onUpdateDraftField: <K extends keyof SessionDraft>(field: K, value: SessionDraft[K]) => void;
  onUpdateEditingDraftField: <K extends keyof SessionEditDraft>(field: K, value: SessionEditDraft[K]) => void;
  onResetDraftEndTime: () => void;
  onCreateDraftSession: () => Promise<void> | void;
  onUpdateEditedSession: () => Promise<void> | void;
  onBackToSession: () => void;
  onOpenEditSessionDraft: (session: SessionDetails) => void;
  onOpenDuplicateSessionDraft: (session: SessionDetails) => void;
  onCancelSelectedSession: () => Promise<void> | void;
  onDeleteSelectedSession: () => Promise<void> | void;
  onJumpToToday: () => void;
}

export function ChronoboardInspector({
  inspectorView,
  draftPlacement,
  draftDatePlans,
  draftSelectionSummary,
  draftWeekdayLabels,
  draftCalendarMonthLabel,
  draftCalendarDays,
  editingDraft,
  selectedSession,
  draftMovie,
  editingMovie,
  movieOptionsForSessionForms,
  isBusy,
  busyActionLabel,
  onDiscardDraft,
  onToggleDraftDate,
  onShowPreviousDraftMonth,
  onShowNextDraftMonth,
  onUpdateDraftField,
  onUpdateEditingDraftField,
  onResetDraftEndTime,
  onCreateDraftSession,
  onUpdateEditedSession,
  onBackToSession,
  onOpenEditSessionDraft,
  onOpenDuplicateSessionDraft,
  onCancelSelectedSession,
  onDeleteSelectedSession,
  onJumpToToday,
}: ChronoboardInspectorProps) {
  const { t, i18n } = useTranslation();
  const isDuplicateDraft = inspectorView === "draft" && draftPlacement?.sourceMode === "duplicate";
  const draftSubmitCount =
    draftSelectionSummary.conflictCount > 0 ? draftSelectionSummary.readyCount : draftSelectionSummary.selectedCount;
  const draftSubmitLabel =
    draftSubmitCount <= 1
      ? t("common.actions.createSession")
      : t("chronoboard.inspector.createSessionsAction", {
          count: draftSubmitCount,
        });

  return (
    <section className="card inspector-panel">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">{t("chronoboard.inspector.eyebrow")}</p>
          <h3 className="section-title">
            {inspectorView === "draft"
              ? isDuplicateDraft
                ? t("chronoboard.inspector.duplicateDraftTitle")
                : t("chronoboard.inspector.pendingDraftTitle")
              : inspectorView === "edit"
                ? t("chronoboard.inspector.editTitle")
                : inspectorView === "session"
                  ? t("chronoboard.inspector.confirmedSessionTitle")
                  : t("chronoboard.inspector.idleTitle")}
          </h3>
          <p className="muted">
            {inspectorView === "draft"
              ? isDuplicateDraft
                ? t("chronoboard.inspector.duplicateDraftIntro")
                : t("chronoboard.inspector.pendingDraftIntro")
              : inspectorView === "session"
                ? t("chronoboard.inspector.confirmedSessionIntro")
                : inspectorView === "edit"
                  ? t("chronoboard.inspector.editIntro")
                  : t("chronoboard.inspector.idleIntro")}
          </p>
        </div>
        {draftPlacement && inspectorView === "draft" ? (
          <button className="button--ghost" type="button" onClick={onDiscardDraft}>
            {t("common.actions.discardDraft")}
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
              <span>{t("common.labels.movie")}</span>
              <select
                required
                disabled={isBusy}
                value={draftPlacement.movie_id}
                onChange={(event) => onUpdateDraftField("movie_id", event.target.value)}
              >
                <option value="">{t("chronoboard.inspector.selectMovieOption")}</option>
                {movieOptionsForSessionForms.map((movie) => (
                  <option key={movie.id} value={movie.id}>
                    {getLocalizedText(movie.title, i18n.language)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("chronoboard.inspector.plannedStart")}</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={draftPlacement.start_time}
                onChange={(event) => onUpdateDraftField("start_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("chronoboard.inspector.calculatedEnd")}</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={draftPlacement.end_time}
                onChange={(event) => onUpdateDraftField("end_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.price")}</span>
              <input
                required
                min={0.01}
                max={1000}
                step="0.01"
                type="number"
                disabled={isBusy}
                value={draftPlacement.price}
                onChange={(event) => onUpdateDraftField("price", Number(event.target.value))}
              />
            </label>
          </div>

          {draftMovie ? (
            <div className="inspector-panel__summary">
              <span className="badge">
                {isDuplicateDraft ? t("chronoboard.inspector.duplicateBadge") : t("chronoboard.inspector.draftBadge")}
              </span>
              <span className="badge">
                {draftMovie.duration_minutes} {t("common.units.minutesShort")}
              </span>
              {draftMovie.age_rating ? <span className="badge">{draftMovie.age_rating}</span> : null}
              <span className="badge">{formatLocalDateTime(draftPlacement.start_time)}</span>
            </div>
          ) : null}

          {!draftPlacement.autoFillEndTime && draftMovie ? (
            <button className="button--ghost" type="button" disabled={isBusy} onClick={onResetDraftEndTime}>
              {t("chronoboard.inspector.resetEndTime")}
            </button>
          ) : null}

          <section className="draft-repeat-panel">
            <div className="draft-repeat-panel__header">
              <div>
                <strong>{t("chronoboard.inspector.repeatDatesTitle")}</strong>
                <p className="muted">
                  {draftPlacement.sourceMode === "timeline"
                    ? t("chronoboard.inspector.repeatDatesDraftMessage")
                    : t("chronoboard.inspector.repeatDatesDuplicateMessage")}
                </p>
              </div>
              <div className="draft-repeat-panel__stats">
                <span className="badge">
                  {t("chronoboard.inspector.selectedDatesCount", {
                    count: draftSelectionSummary.selectedCount,
                  })}
                </span>
                <span className="badge">
                  {t("chronoboard.inspector.readyDatesCount", {
                    count: draftSelectionSummary.readyCount,
                  })}
                </span>
                {draftSelectionSummary.conflictCount > 0 ? (
                  <span className="badge badge--warning">
                    {t("chronoboard.inspector.conflictingDatesCount", {
                      count: draftSelectionSummary.conflictCount,
                    })}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="draft-repeat-panel__month-bar">
              <button
                className="button--ghost"
                type="button"
                disabled={isBusy}
                onClick={onShowPreviousDraftMonth}
                aria-label={t("chronoboard.inspector.previousMonth")}
              >
                &lt;
              </button>
              <strong>{draftCalendarMonthLabel}</strong>
              <button
                className="button--ghost"
                type="button"
                disabled={isBusy}
                onClick={onShowNextDraftMonth}
                aria-label={t("chronoboard.inspector.nextMonth")}
              >
                &gt;
              </button>
            </div>

            <div className="draft-repeat-panel__weekday-row" aria-hidden="true">
              {draftWeekdayLabels.map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>

            <div className="draft-repeat-panel__calendar">
              {draftCalendarDays.map((day) => (
                <button
                  key={day.dateKey}
                  className={[
                    "draft-repeat-panel__day",
                    day.isSelected ? "is-selected" : "",
                    day.isLocked ? "is-locked" : "",
                    day.isPast ? "is-past" : "",
                    day.hasConflict ? "is-conflict" : "",
                    day.hasSessions ? "has-sessions" : "",
                    !day.isCurrentMonth ? "is-outside" : "",
                    day.isToday ? "is-today" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  type="button"
                  disabled={isBusy || day.isLocked}
                  onClick={() => onToggleDraftDate(day.dateKey)}
                >
                  <span>{day.dayNumber}</span>
                </button>
              ))}
            </div>

            <div className="draft-repeat-panel__chips">
              {draftDatePlans.length > 0 ? (
                draftDatePlans.map((plan) => (
                  <button
                    key={plan.dateKey}
                    className={[
                      "draft-repeat-panel__chip",
                      plan.isConflicting ? "is-conflict" : "",
                      plan.isLocked ? "is-locked" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    type="button"
                    disabled={isBusy || plan.isLocked}
                    onClick={() => onToggleDraftDate(plan.dateKey)}
                  >
                    <strong>{plan.shortLabel}</strong>
                    <span>
                      {formatTime(plan.startTime)} - {formatTime(plan.endTime)}
                    </span>
                  </button>
                ))
              ) : (
                <p className="muted">{t("chronoboard.inspector.emptyDateSelection")}</p>
              )}
            </div>

            {draftSelectionSummary.conflictCount > 0 ? (
              <div className="draft-repeat-panel__issues">
                <strong>{t("chronoboard.inspector.conflictListTitle")}</strong>
                {draftDatePlans
                  .filter((plan) => plan.isConflicting)
                  .map((plan) => (
                    <div key={plan.dateKey} className="draft-repeat-panel__issue">
                      <span>{plan.shortLabel}</span>
                      <span>{plan.conflictReason}</span>
                    </div>
                  ))}
              </div>
            ) : null}

            {draftSelectionSummary.conflictCount > 0 && draftSelectionSummary.readyCount > 0 ? (
              <p className="muted">
                {t("chronoboard.inspector.partialCreateHint", {
                  readyCount: draftSelectionSummary.readyCount,
                  conflictCount: draftSelectionSummary.conflictCount,
                })}
              </p>
            ) : null}
          </section>

          <div className="actions-row">
            <button
              className="button"
              type="submit"
              disabled={isBusy || draftSelectionSummary.selectedCount === 0 || draftSelectionSummary.readyCount === 0}
            >
              {draftSubmitLabel}
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
              <span>{t("common.labels.movie")}</span>
              <select
                required
                disabled={isBusy}
                value={editingDraft.movie_id}
                onChange={(event) => onUpdateEditingDraftField("movie_id", event.target.value)}
              >
                <option value="">{t("chronoboard.inspector.selectMovieOption")}</option>
                {movieOptionsForSessionForms.map((movie) => (
                  <option key={movie.id} value={movie.id}>
                    {getLocalizedText(movie.title, i18n.language)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("common.labels.startsAt")}</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={editingDraft.start_time}
                onChange={(event) => onUpdateEditingDraftField("start_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.endsAt")}</span>
              <input
                required
                type="datetime-local"
                disabled={isBusy}
                value={editingDraft.end_time}
                onChange={(event) => onUpdateEditingDraftField("end_time", event.target.value)}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.price")}</span>
              <input
                required
                min={0.01}
                max={1000}
                step="0.01"
                type="number"
                disabled={isBusy}
                value={editingDraft.price}
                onChange={(event) => onUpdateEditingDraftField("price", Number(event.target.value))}
              />
            </label>
          </div>

          {editingMovie ? (
            <div className="inspector-panel__summary">
              <span className="badge">{t("chronoboard.inspector.editingSavedSession")}</span>
              <span className="badge">
                {editingMovie.duration_minutes} {t("common.units.minutesShort")}
              </span>
              <span className="badge">{formatLocalDateTime(editingDraft.start_time)}</span>
            </div>
          ) : null}

          <div className="actions-row">
            <button className="button" type="submit" disabled={isBusy}>
              {t("common.actions.saveSessionChanges")}
            </button>
            <button className="button--ghost" type="button" disabled={isBusy} onClick={onBackToSession}>
              {t("common.actions.backToSession")}
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
                <span>{getMovieMonogram(getLocalizedText(selectedSession.movie.title, i18n.language))}</span>
              )}
            </div>
            <div>
              <strong>{getLocalizedText(selectedSession.movie.title, i18n.language)}</strong>
              <p className="muted">
                {formatDateTime(selectedSession.start_time)} - {formatTime(selectedSession.end_time)}
              </p>
            </div>
          </div>

          <div className="stats-row">
            <span className="badge">{formatStateLabel(selectedSession.status)}</span>
            <span className="badge">{formatCurrency(selectedSession.price)}</span>
            <span className="badge">
              {t("chronoboard.inspector.soldCount", {
                count: selectedSession.total_seats - selectedSession.available_seats,
              })}
            </span>
            <span className="badge">
              {t("chronoboard.inspector.leftCount", {
                available: selectedSession.available_seats,
                total: selectedSession.total_seats,
              })}
            </span>
          </div>

          <p className="muted">{getLocalizedText(selectedSession.movie.description, i18n.language)}</p>

          <div className="stats-row">
            {selectedSession.movie.age_rating ? <span className="badge">{selectedSession.movie.age_rating}</span> : null}
            {selectedSession.movie.genres.length > 0 ? (
              <span className="badge">
                {getGenreLabels(selectedSession.movie.genres, i18n.language).join(", ")}
              </span>
            ) : null}
          </div>

          <div className="actions-row">
            <button
              className="button--ghost"
              type="button"
              disabled={isBusy}
              onClick={() => onOpenDuplicateSessionDraft(selectedSession)}
            >
              {t("common.actions.duplicateToDates")}
            </button>
            <button
              className="button--ghost"
              type="button"
              disabled={isBusy}
              onClick={() => onOpenEditSessionDraft(selectedSession)}
            >
              {t("common.actions.editSession")}
            </button>
            <button
              className="button--ghost"
              type="button"
              disabled={isBusy || selectedSession.status !== "scheduled"}
              onClick={() => void onCancelSelectedSession()}
            >
              {t("common.actions.cancelSession")}
            </button>
            <button
              className="button--danger"
              type="button"
              disabled={isBusy}
              onClick={() => void onDeleteSelectedSession()}
            >
              {t("common.actions.deleteSession")}
            </button>
          </div>
        </div>
      ) : null}

      {inspectorView === "none" ? (
        <StatePanel
          title={t("chronoboard.inspector.idlePanelTitle")}
          message={t("chronoboard.inspector.idlePanelMessage")}
          action={
            <button className="button--ghost" type="button" onClick={onJumpToToday}>
              {t("common.actions.jumpToToday")}
            </button>
          }
        />
      ) : null}
    </section>
  );
}
