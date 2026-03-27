import type { SessionDraft } from "@/widgets/admin/chronoboard/types";

export const DRAG_MOVIE_MIME = "text/cinema-showcase-movie-id";
export const BOARD_START_HOUR = 9;
export const BOARD_END_HOUR = 24;
export const LAST_SESSION_START_HOUR = 22;
export const SLOT_MINUTES = 30;
export const PIXELS_PER_MINUTE = 1.8;
export const BOARD_TOTAL_MINUTES = (BOARD_END_HOUR - BOARD_START_HOUR) * 60;
export const BOARD_WIDTH = BOARD_TOTAL_MINUTES * PIXELS_PER_MINUTE;

export function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function toDateKey(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatDayLabel(dayKey: string): string {
  const [year, month, day] = dayKey.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });
}

export function formatLocalDateTime(value: string): string {
  return new Date(value).toLocaleString([], {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function toDateTimeLocal(value: string): string {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function addMinutesToDateTimeLocal(value: string, minutes: number): string {
  if (!value) {
    return value;
  }

  const date = new Date(value);
  date.setMinutes(date.getMinutes() + minutes);
  return toDateTimeLocal(date.toISOString());
}

export function getBoardMinuteOffset(date: Date): number {
  return (date.getHours() - BOARD_START_HOUR) * 60 + date.getMinutes();
}

export function clampMinutes(value: number): number {
  return Math.min(Math.max(value, 0), BOARD_TOTAL_MINUTES);
}

export function buildDayDate(dayKey: string, hour: number, minute: number): string {
  return `${dayKey}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

export function getSessionCardStyle(startTime: string, endTime: string): { left: string; width: string } {
  const startDate = new Date(startTime);
  const endDate = new Date(endTime);
  const startOffset = clampMinutes(getBoardMinuteOffset(startDate));
  const durationMinutes = Math.max((endDate.getTime() - startDate.getTime()) / 60000, SLOT_MINUTES);

  return {
    left: `${startOffset * PIXELS_PER_MINUTE}px`,
    width: `${Math.max(durationMinutes * PIXELS_PER_MINUTE, SLOT_MINUTES * PIXELS_PER_MINUTE)}px`,
  };
}

export function getDraftDurationMinutes(draft: Pick<SessionDraft, "start_time" | "end_time">): number {
  const startDate = new Date(draft.start_time);
  const endDate = new Date(draft.end_time);

  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return SLOT_MINUTES;
  }

  return Math.max(Math.round((endDate.getTime() - startDate.getTime()) / 60000), SLOT_MINUTES);
}
