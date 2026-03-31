import type { Movie, MovieStatus } from "@/types/domain";

export function isMovieActive(movie: Pick<Movie, "status">): boolean {
  return movie.status === "active";
}

export function isMovieScheduleReady(movie: Pick<Movie, "status">): boolean {
  return movie.status !== "deactivated";
}

export function getMovieStatusPriority(status: MovieStatus): number {
  switch (status) {
    case "active":
      return 0;
    case "planned":
      return 1;
    case "deactivated":
      return 2;
    default:
      return 3;
  }
}

export function getMovieStatusTranslationKey(status: MovieStatus): string {
  switch (status) {
    case "active":
      return "activeLabel";
    case "planned":
      return "plannedLabel";
    case "deactivated":
      return "deactivatedLabel";
    default:
      return status;
  }
}

export function getMovieStatusBadgeClassName(status: MovieStatus): string {
  switch (status) {
    case "active":
      return "badge badge--active";
    case "planned":
      return "badge badge--planned";
    case "deactivated":
      return "badge badge--danger";
    default:
      return "badge";
  }
}
