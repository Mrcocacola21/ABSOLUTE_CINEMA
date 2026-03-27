export const PUBLIC_SCHEDULE_START_HOUR = 9;
export const PUBLIC_SCHEDULE_END_HOUR = 24;
export const PUBLIC_SCHEDULE_PIXELS_PER_MINUTE = 1.35;
export const PUBLIC_SCHEDULE_TOTAL_MINUTES =
  (PUBLIC_SCHEDULE_END_HOUR - PUBLIC_SCHEDULE_START_HOUR) * 60;
export const PUBLIC_SCHEDULE_BOARD_WIDTH =
  PUBLIC_SCHEDULE_TOTAL_MINUTES * PUBLIC_SCHEDULE_PIXELS_PER_MINUTE;

export function toScheduleDayKey(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatScheduleDayLabel(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    weekday: "short",
    day: "2-digit",
    month: "short",
  });
}

export function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function getScheduleDurationMinutes(startTime: string, endTime: string): number {
  const startDate = new Date(startTime);
  const endDate = new Date(endTime);
  return Math.max((endDate.getTime() - startDate.getTime()) / 60000, 30);
}

function getBoardMinuteOffset(date: Date): number {
  return (date.getHours() - PUBLIC_SCHEDULE_START_HOUR) * 60 + date.getMinutes();
}

function clampMinutes(value: number): number {
  return Math.min(Math.max(value, 0), PUBLIC_SCHEDULE_TOTAL_MINUTES);
}

export function getPublicScheduleCardMetrics(startTime: string, endTime: string): {
  left: number;
  width: number;
} {
  const startDate = new Date(startTime);
  const startOffset = clampMinutes(getBoardMinuteOffset(startDate));
  const durationMinutes = getScheduleDurationMinutes(startTime, endTime);

  return {
    left: startOffset * PUBLIC_SCHEDULE_PIXELS_PER_MINUTE,
    width: Math.max(durationMinutes * PUBLIC_SCHEDULE_PIXELS_PER_MINUTE, 120),
  };
}

export function getPublicScheduleCardStyle(startTime: string, endTime: string): { left: string; width: string } {
  const metrics = getPublicScheduleCardMetrics(startTime, endTime);

  return {
    left: `${metrics.left}px`,
    width: `${metrics.width}px`,
  };
}

export function getNowMarkerOffsetForScheduleDay(dayKey: string): string | null {
  if (dayKey !== toScheduleDayKey(new Date())) {
    return null;
  }

  const boardOffset = getBoardMinuteOffset(new Date());
  if (boardOffset < 0 || boardOffset > PUBLIC_SCHEDULE_TOTAL_MINUTES) {
    return null;
  }

  return `${boardOffset * PUBLIC_SCHEDULE_PIXELS_PER_MINUTE}px`;
}
