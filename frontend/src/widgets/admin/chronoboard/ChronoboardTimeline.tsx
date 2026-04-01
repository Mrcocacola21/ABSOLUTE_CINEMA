import type { DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatStateLabel, formatTime } from "@/shared/presentation";
import type { Movie, SessionDetails } from "@/types/domain";
import type {
  BoardSlot,
  DragOrigin,
  DragPreview,
  InspectorView,
  SessionDraft,
} from "@/widgets/admin/chronoboard/types";
import {
  BOARD_END_HOUR,
  BOARD_START_HOUR,
  BOARD_WIDTH,
  PIXELS_PER_MINUTE,
  getSessionCardStyle,
} from "@/widgets/admin/chronoboard/utils";

interface ChronoboardTimelineProps {
  candidateMovie: Movie | null;
  draggedMovieId: string | null;
  boardSlots: BoardSlot[];
  nowMarkerOffset: string | null;
  previewMovie: Movie | null;
  dragPreview: DragPreview | null;
  previewEndTime: string | null;
  previewDurationMinutes: number | null;
  dragOrigin: DragOrigin | null;
  visibleDraft: SessionDraft | null;
  draftMovie: Movie | null;
  inspectorView: InspectorView;
  isDraggingDraft: boolean;
  selectedDaySessions: SessionDetails[];
  selectedSessionId: string | null;
  isBusy: boolean;
  onLaneDragLeave: (event: DragEvent<HTMLDivElement>) => void;
  onSlotClick: (startTime: string) => void;
  onSlotDragOver: (event: DragEvent<HTMLButtonElement>, slot: BoardSlot) => void;
  onSlotDrop: (event: DragEvent<HTMLButtonElement>, slot: BoardSlot) => void;
  onDraftDragStart: (event: DragEvent<HTMLButtonElement>) => void;
  onDragEnd: () => void;
  onDraftSelect: () => void;
  onSessionSelect: (session: SessionDetails) => void;
}

const boardHourMarkers = Array.from({ length: BOARD_END_HOUR - BOARD_START_HOUR + 1 }, (_, index) => {
  const hour = BOARD_START_HOUR + index;
  return {
    label: `${String(hour).padStart(2, "0")}:00`,
    left: `${(hour - BOARD_START_HOUR) * 60 * PIXELS_PER_MINUTE}px`,
  };
});

const boardHourLines = Array.from({ length: BOARD_END_HOUR - BOARD_START_HOUR + 1 }, (_, index) => ({
  key: index,
  left: `${index * 60 * PIXELS_PER_MINUTE}px`,
}));

export function ChronoboardTimeline({
  candidateMovie,
  draggedMovieId,
  boardSlots,
  nowMarkerOffset,
  previewMovie,
  dragPreview,
  previewEndTime,
  previewDurationMinutes,
  dragOrigin,
  visibleDraft,
  draftMovie,
  inspectorView,
  isDraggingDraft,
  selectedDaySessions,
  selectedSessionId,
  isBusy,
  onLaneDragLeave,
  onSlotClick,
  onSlotDragOver,
  onSlotDrop,
  onDraftDragStart,
  onDragEnd,
  onDraftSelect,
  onSessionSelect,
}: ChronoboardTimelineProps) {
  const { i18n } = useTranslation();

  return (
    <section className="card chrono-stage">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">Timeline</p>
          <h3 className="section-title">Drag to place, then confirm</h3>
          <p className="muted">
            Gray blocks are drafts or previews. Only saved sessions use the normal session styling.
          </p>
        </div>
        <div className="stats-row">
          {candidateMovie ? (
            <span className="badge">{getLocalizedText(candidateMovie.title, i18n.language)}</span>
          ) : (
            <span className="badge">Select a movie to plan</span>
          )}
        </div>
      </div>

      <div className="chrono-stage__frame">
        <div className="chrono-board" style={{ width: `${BOARD_WIDTH}px` }}>
          <div className="chrono-board__scale">
            {boardHourMarkers.map((marker) => (
              <div key={marker.label} className="chrono-board__hour-label" style={{ left: marker.left }}>
                {marker.label}
              </div>
            ))}
          </div>

          <div
            className={`chrono-board__lane${draggedMovieId ? " is-dragging" : ""}`}
            onDragLeave={onLaneDragLeave}
          >
            {boardHourLines.map((line) => (
              <div key={line.key} className="chrono-board__hour-line" style={{ left: line.left }} />
            ))}

            {boardSlots.map((slot) => (
              <button
                key={slot.key}
                type="button"
                className={[
                  "chrono-board__slot",
                  candidateMovie && !slot.blockedReason ? "is-available" : "",
                  candidateMovie && slot.blockedReason ? "is-blocked" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={{ left: slot.left, width: slot.width }}
                onClick={() => onSlotClick(slot.startTime)}
                onDragOver={(event) => onSlotDragOver(event, slot)}
                onDrop={(event) => onSlotDrop(event, slot)}
                aria-label={`Plan a movie at ${slot.label}`}
              />
            ))}

            {nowMarkerOffset ? (
              <div className="chrono-board__now" style={{ left: nowMarkerOffset }}>
                <span>Now</span>
              </div>
            ) : null}

            {previewMovie && dragPreview && previewEndTime ? (
              <div
                className="chrono-session chrono-session--preview"
                style={getSessionCardStyle(dragPreview.startTime, previewEndTime)}
              >
                <div className="chrono-session__header">
                  <strong title={getLocalizedText(previewMovie.title, i18n.language)}>
                    {getLocalizedText(previewMovie.title, i18n.language)}
                  </strong>
                  <span className="badge">Preview</span>
                </div>
                <p className="chrono-session__time">
                  {formatTime(dragPreview.startTime)} - {formatTime(previewEndTime)}
                </p>
                <div className="chrono-session__footer">
                  {previewDurationMinutes ? <span className="badge">{previewDurationMinutes} min</span> : null}
                  <p className="chrono-session__meta">
                    {dragOrigin === "draft" ? "Drop to move draft" : "Drop to stage a draft"}
                  </p>
                </div>
              </div>
            ) : null}

            {visibleDraft && draftMovie ? (
              <button
                type="button"
                className={[
                  "chrono-session",
                  "chrono-session--draft",
                  inspectorView === "draft" ? "is-selected" : "",
                  isDraggingDraft ? "is-drag-lifted" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={getSessionCardStyle(visibleDraft.start_time, visibleDraft.end_time)}
                draggable={!isBusy}
                onDragStart={onDraftDragStart}
                onDragEnd={onDragEnd}
                onClick={onDraftSelect}
              >
                <div className="chrono-session__header">
                  <strong title={getLocalizedText(draftMovie.title, i18n.language)}>
                    {getLocalizedText(draftMovie.title, i18n.language)}
                  </strong>
                  <span className="badge">Draft</span>
                </div>
                <p className="chrono-session__time">
                  {formatTime(visibleDraft.start_time)} - {formatTime(visibleDraft.end_time)}
                </p>
                <div className="chrono-session__footer">
                  <span className="badge chrono-session__price">{formatCurrency(visibleDraft.price)}</span>
                  <p className="chrono-session__meta">Pending confirmation</p>
                </div>
              </button>
            ) : null}

            {selectedDaySessions.map((session) => {
              const soldTickets = session.total_seats - session.available_seats;
              const isSelected = selectedSessionId === session.id && inspectorView !== "draft";

              return (
                <button
                  key={session.id}
                  type="button"
                  className={`chrono-session chrono-session--${session.status}${isSelected ? " is-selected" : ""}`}
                  style={getSessionCardStyle(session.start_time, session.end_time)}
                  onClick={() => onSessionSelect(session)}
                >
                  <div className="chrono-session__header">
                    <strong title={getLocalizedText(session.movie.title, i18n.language)}>
                      {getLocalizedText(session.movie.title, i18n.language)}
                    </strong>
                    <span className="badge">{formatStateLabel(session.status)}</span>
                  </div>
                  <p className="chrono-session__time">
                    {formatTime(session.start_time)} - {formatTime(session.end_time)}
                  </p>
                  <div className="chrono-session__footer">
                    <span className="badge chrono-session__price">{formatCurrency(session.price)}</span>
                    <p className="chrono-session__meta">
                      {soldTickets} sold / {session.available_seats}/{session.total_seats} left
                    </p>
                  </div>
                </button>
              );
            })}

            {selectedDaySessions.length === 0 && !visibleDraft ? (
              <div className="chrono-board__empty">
                <strong>No confirmed sessions on this day yet</strong>
                <span>Drag a movie onto the timeline to stage the first draft for this board.</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
