export type SessionDraftSourceMode = "timeline" | "duplicate";

export interface SessionDraft {
  movie_id: string;
  start_time: string;
  end_time: string;
  price: number;
  autoFillEndTime: boolean;
  sourceLabel: string;
  sourceMode: SessionDraftSourceMode;
  extraDateKeys: string[];
  calendarMonth: string;
}

export interface SessionEditDraft {
  sessionId: string;
  movie_id: string;
  start_time: string;
  end_time: string;
  price: number;
  autoFillEndTime: boolean;
  sourceLabel: string;
}

export interface DragPreview {
  movieId: string;
  startTime: string;
}

export interface PlannerNotice {
  scope: "planning" | "session";
  tone: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
}

export type InspectorView = "none" | "draft" | "session" | "edit";
export type DragOrigin = "shelf" | "draft";

export interface BoardSlot {
  key: string;
  startTime: string;
  label: string;
  left: string;
  width: string;
  blockedReason: string | null;
  blockingSessionId: string | null;
}

export interface QuickDayOption {
  value: string;
  label: string;
  count: number;
}

export interface BoardStats {
  sessions: number;
  soldTickets: number;
  availableSeats: number;
}

export interface DraftDatePlan {
  dateKey: string;
  label: string;
  shortLabel: string;
  startTime: string;
  endTime: string;
  isLocked: boolean;
  isConflicting: boolean;
  conflictReason: string | null;
}

export interface DraftCalendarDay {
  dateKey: string;
  dayNumber: string;
  isCurrentMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
  isLocked: boolean;
  isPast: boolean;
  hasConflict: boolean;
  hasSessions: boolean;
}
