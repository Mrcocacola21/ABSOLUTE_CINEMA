import { buildGenreSearchText, getGenreLabel, type GenreCode } from "@/shared/genres";
import {
  buildLocalizedSearchText,
  compareLocalizedText,
  getLocalizedText,
} from "@/shared/localization";
import { formatScheduleDayLabel, toScheduleDayKey } from "@/shared/scheduleTimeline";
import { getMovieStatusPriority, isMovieActive } from "@/shared/movieStatus";
import type { LocalizedText, Movie, MovieStatus, ScheduleItem } from "@/types/domain";

export interface MovieOption {
  id: string;
  title: string;
}

export interface ScheduleDayOption {
  value: string;
  label: string;
  count: number;
}

export type ScheduleDateSortMode = "nearest" | "farthest";
export type ScheduleSeatSortMode = "" | "most_occupied" | "least_occupied";

export interface RotationMovie {
  id: string;
  title: LocalizedText;
  description: LocalizedText;
  poster_url?: string | null;
  age_rating?: string | null;
  genres: GenreCode[];
  status: MovieStatus;
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

function getScheduleItemTitle(item: ScheduleItem, language: string): string {
  return getLocalizedText(item.movie_title, language);
}

export function filterScheduleItems(
  items: ScheduleItem[],
  query: string,
  movieId: string,
  language: string,
): ScheduleItem[] {
  const normalizedQuery = query.trim().toLowerCase();

  return items.filter((item) => {
    if (movieId && item.movie_id !== movieId) {
      return false;
    }

    if (!normalizedQuery) {
      return true;
    }

    return getScheduleItemTitle(item, language).toLowerCase().includes(normalizedQuery);
  });
}

export function filterBoardScheduleItems(
  items: ScheduleItem[],
  movieId: string,
  genre: GenreCode | "",
): ScheduleItem[] {
  return items.filter((item) => {
    if (movieId && item.movie_id !== movieId) {
      return false;
    }

    if (genre && !item.genres.includes(genre)) {
      return false;
    }

    return true;
  });
}

export function filterScheduleListItems(
  items: ScheduleItem[],
  query: string,
  day: string,
  language: string,
): ScheduleItem[] {
  const normalizedQuery = query.trim().toLowerCase();

  return items.filter((item) => {
    if (day && toScheduleDayKey(item.start_time) !== day) {
      return false;
    }

    if (!normalizedQuery) {
      return true;
    }

    return getScheduleItemTitle(item, language).toLowerCase().includes(normalizedQuery);
  });
}

export function sortScheduleItems(
  items: ScheduleItem[],
  sortBy: string,
  sortOrder: string,
  language: string,
): ScheduleItem[] {
  return [...items].sort((left, right) => {
    if (sortBy === "available_seats") {
      const seatComparison = compareValues(left.available_seats, right.available_seats, sortOrder);
      if (seatComparison !== 0) {
        return seatComparison;
      }
    } else if (sortBy === "occupied_seats") {
      const leftOccupiedSeats = left.total_seats - left.available_seats;
      const rightOccupiedSeats = right.total_seats - right.available_seats;
      const seatComparison = compareValues(leftOccupiedSeats, rightOccupiedSeats, sortOrder);
      if (seatComparison !== 0) {
        return seatComparison;
      }
    } else if (sortBy === "movie_title") {
      const titleComparison = compareText(
        getScheduleItemTitle(left, language),
        getScheduleItemTitle(right, language),
        sortOrder,
      );
      if (titleComparison !== 0) {
        return titleComparison;
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

    return compareText(getScheduleItemTitle(left, language), getScheduleItemTitle(right, language), "asc");
  });
}

export function sortPublicScheduleListItems(
  items: ScheduleItem[],
  dateSort: ScheduleDateSortMode,
  seatSort: ScheduleSeatSortMode,
  language: string,
): ScheduleItem[] {
  const normalizedSeatSort = seatSort.trim();
  const dateDirection = dateSort === "farthest" ? "desc" : "asc";

  return [...items].sort((left, right) => {
    const leftDay = toScheduleDayKey(left.start_time);
    const rightDay = toScheduleDayKey(right.start_time);
    const dayComparison = compareText(leftDay, rightDay, dateDirection);

    if (dayComparison !== 0) {
      return dayComparison;
    }

    if (normalizedSeatSort === "most_occupied" || normalizedSeatSort === "least_occupied") {
      const leftOccupiedSeats = left.total_seats - left.available_seats;
      const rightOccupiedSeats = right.total_seats - right.available_seats;
      const seatComparison = compareValues(
        leftOccupiedSeats,
        rightOccupiedSeats,
        normalizedSeatSort === "most_occupied" ? "desc" : "asc",
      );

      if (seatComparison !== 0) {
        return seatComparison;
      }
    }

    const timeComparison = compareValues(
      new Date(left.start_time).getTime(),
      new Date(right.start_time).getTime(),
      dateDirection,
    );

    if (timeComparison !== 0) {
      return timeComparison;
    }

    return compareText(getScheduleItemTitle(left, language), getScheduleItemTitle(right, language), "asc");
  });
}

export function getAvailableMovieOptions(items: ScheduleItem[], language: string): MovieOption[] {
  const movieMap = new Map<string, LocalizedText>();

  for (const item of items) {
    if (!movieMap.has(item.movie_id)) {
      movieMap.set(item.movie_id, item.movie_title);
    }
  }

  return [...movieMap.entries()]
    .map(([id, title]) => ({ id, title: getLocalizedText(title, language) }))
    .sort((left, right) => left.title.localeCompare(right.title));
}

export function getAvailableGenreOptions(items: ScheduleItem[], language: string): GenreCode[] {
  const genres = new Set<GenreCode>();

  for (const item of items) {
    for (const genre of item.genres) {
      genres.add(genre);
    }
  }

  return [...genres].sort((left, right) =>
    getGenreLabel(left, language).localeCompare(getGenreLabel(right, language)),
  );
}

export function getScheduleDayOptions(items: ScheduleItem[]): ScheduleDayOption[] {
  const days = new Map<string, number>();

  for (const item of items) {
    const dayKey = toScheduleDayKey(item.start_time);
    days.set(dayKey, (days.get(dayKey) ?? 0) + 1);
  }

  return [...days.entries()]
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([value, count]) => ({
      value,
      label: formatScheduleDayLabel(value),
      count,
    }));
}

export function getScheduleTitleSuggestions(
  items: ScheduleItem[],
  query: string,
  language: string,
  limit = 8,
): string[] {
  const titles = [...new Set(items.map((item) => getScheduleItemTitle(item, language)))].sort((left, right) =>
    left.localeCompare(right),
  );
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) {
    return titles.slice(0, limit);
  }

  return titles
    .filter((title) => title.toLowerCase().includes(normalizedQuery))
    .slice(0, limit);
}

export function buildRotationMovies(
  items: ScheduleItem[],
  moviesById: Record<string, Movie>,
  sortBy: string,
  sortOrder: string,
  language: string,
): RotationMovie[] {
  const groupedItems = new Map<string, ScheduleItem[]>();

  for (const item of items) {
    const existingItems = groupedItems.get(item.movie_id) ?? [];
    existingItems.push(item);
    groupedItems.set(item.movie_id, existingItems);
  }

  const rotationMovies: RotationMovie[] = [];

  for (const [movieId, movieItems] of groupedItems.entries()) {
    const sortedItems = sortScheduleItems(movieItems, "start_time", "asc", language);
    const nextSession = sortedItems[0];
    const lastSession = sortedItems[sortedItems.length - 1];
    const movie = moviesById[movieId];

    if (!movie || !isMovieActive(movie)) {
      continue;
    }

    const prices = movieItems.map((item) => item.price);
    const availableSeatCounts = movieItems.map((item) => item.available_seats);

    rotationMovies.push({
      id: movieId,
      title: movie.title,
      description: movie.description,
      poster_url: movie.poster_url ?? nextSession.poster_url,
      age_rating: movie.age_rating ?? nextSession.age_rating,
      genres: movie.genres.length ? movie.genres : nextSession.genres,
      status: movie.status,
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

    const statusComparison = getMovieStatusPriority(left.status) - getMovieStatusPriority(right.status);
    if (statusComparison !== 0) {
      return statusComparison;
    }

    return compareLocalizedText(left.title, right.title, language);
  });
}

export function buildMovieSearchText(movie: Movie): string {
  return [
    buildLocalizedSearchText(movie.title),
    buildLocalizedSearchText(movie.description),
    movie.age_rating ?? "",
    ...movie.genres.map((genre) => buildGenreSearchText(genre)),
  ]
    .join(" ")
    .toLowerCase();
}
