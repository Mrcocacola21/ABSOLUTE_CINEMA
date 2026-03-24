import type { Movie, ScheduleItem } from "@/types/domain";

export interface MovieOption {
  id: string;
  title: string;
}

export interface RotationMovie {
  id: string;
  title: string;
  description?: string;
  poster_url?: string | null;
  age_rating?: string | null;
  genres: string[];
  is_active: boolean;
  nextSession: ScheduleItem;
  lastSession: ScheduleItem;
  upcomingSessions: number;
  maxAvailableSeats: number;
  minPrice: number;
  maxPrice: number;
}

function compareValues(left: number, right: number, sortOrder: string): number {
  return sortOrder === "desc" ? right - left : left - right;
}

function compareText(left: string, right: string, sortOrder: string): number {
  return sortOrder === "desc" ? right.localeCompare(left) : left.localeCompare(right);
}

export function filterScheduleItems(
  items: ScheduleItem[],
  query: string,
  movieId: string,
): ScheduleItem[] {
  const normalizedQuery = query.trim().toLowerCase();

  return items.filter((item) => {
    if (movieId && item.movie_id !== movieId) {
      return false;
    }

    if (!normalizedQuery) {
      return true;
    }

    return item.movie_title.toLowerCase().includes(normalizedQuery);
  });
}

export function sortScheduleItems(
  items: ScheduleItem[],
  sortBy: string,
  sortOrder: string,
): ScheduleItem[] {
  return [...items].sort((left, right) => {
    if (sortBy === "available_seats") {
      const seatComparison = compareValues(left.available_seats, right.available_seats, sortOrder);
      if (seatComparison !== 0) {
        return seatComparison;
      }
    } else {
      const timeComparison = compareValues(
        new Date(left.start_time).getTime(),
        new Date(right.start_time).getTime(),
        sortOrder,
      );
      if (timeComparison !== 0) {
        return timeComparison;
      }
    }

    return compareText(left.movie_title, right.movie_title, "asc");
  });
}

export function getAvailableMovieOptions(items: ScheduleItem[]): MovieOption[] {
  const movieMap = new Map<string, string>();

  for (const item of items) {
    if (!movieMap.has(item.movie_id)) {
      movieMap.set(item.movie_id, item.movie_title);
    }
  }

  return [...movieMap.entries()]
    .map(([id, title]) => ({ id, title }))
    .sort((left, right) => left.title.localeCompare(right.title));
}

export function buildRotationMovies(
  items: ScheduleItem[],
  moviesById: Record<string, Movie>,
  sortBy: string,
  sortOrder: string,
): RotationMovie[] {
  const groupedItems = new Map<string, ScheduleItem[]>();

  for (const item of items) {
    const existingItems = groupedItems.get(item.movie_id) ?? [];
    existingItems.push(item);
    groupedItems.set(item.movie_id, existingItems);
  }

  const rotationMovies: RotationMovie[] = [];

  for (const [movieId, movieItems] of groupedItems.entries()) {
    const sortedItems = sortScheduleItems(movieItems, "start_time", "asc");
    const nextSession = sortedItems[0];
    const lastSession = sortedItems[sortedItems.length - 1];
    const movie = moviesById[movieId];

    if (!movie || !movie.is_active) {
      continue;
    }

    const prices = movieItems.map((item) => item.price);
    const availableSeatCounts = movieItems.map((item) => item.available_seats);

    rotationMovies.push({
      id: movieId,
      title: nextSession.movie_title,
      description: movie.description,
      poster_url: movie.poster_url ?? nextSession.poster_url,
      age_rating: movie.age_rating ?? nextSession.age_rating,
      genres: movie.genres.length ? movie.genres : nextSession.genres,
      is_active: movie.is_active,
      nextSession,
      lastSession,
      upcomingSessions: movieItems.length,
      maxAvailableSeats: Math.max(...availableSeatCounts),
      minPrice: Math.min(...prices),
      maxPrice: Math.max(...prices),
    });
  }

  return rotationMovies.sort((left, right) => {
      if (sortBy === "available_seats") {
        const seatComparison = compareValues(left.maxAvailableSeats, right.maxAvailableSeats, sortOrder);
        if (seatComparison !== 0) {
          return seatComparison;
        }
      } else {
        const timeComparison = compareValues(
          new Date(left.nextSession.start_time).getTime(),
          new Date(right.nextSession.start_time).getTime(),
          sortOrder,
        );
        if (timeComparison !== 0) {
          return timeComparison;
        }
      }

      return compareText(left.title, right.title, "asc");
    });
}
