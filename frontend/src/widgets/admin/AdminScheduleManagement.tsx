import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import type {
  MovieCreatePayload,
  MovieUpdatePayload,
  SessionCreatePayload,
  SessionUpdatePayload,
} from "@/api/admin";
import { formatCurrency, formatDateTime, formatStateLabel, formatTime } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { Movie, Session, SessionDetails } from "@/types/domain";

interface AdminScheduleManagementProps {
  movies: Movie[];
  sessions: SessionDetails[];
  isBusy: boolean;
  busyActionLabel?: string;
  onCreateMovie: (payload: MovieCreatePayload) => Promise<Movie | null>;
  onUpdateMovie: (movieId: string, payload: MovieUpdatePayload) => Promise<Movie | null>;
  onDeactivateMovie: (movieId: string) => Promise<Movie | null>;
  onDeleteMovie: (movieId: string) => Promise<{ id: string; deleted: boolean } | null>;
  onCreateSession: (payload: SessionCreatePayload) => Promise<SessionDetails | null>;
  onUpdateSession: (sessionId: string, payload: SessionUpdatePayload) => Promise<SessionDetails | null>;
  onCancelSession: (sessionId: string) => Promise<Session | null>;
  onDeleteSession: (sessionId: string) => Promise<{ id: string; deleted: boolean } | null>;
}

interface SessionDraft {
  movie_id: string;
  start_time: string;
  end_time: string;
  price: number;
  autoFillEndTime: boolean;
  sourceLabel: string;
}

interface SessionEditDraft extends SessionDraft {
  sessionId: string;
}

interface DragPreview {
  movieId: string;
  startTime: string;
}

interface PlannerNotice {
  scope: "planning" | "session";
  tone: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
}

type InspectorView = "none" | "draft" | "session" | "edit";
type DragOrigin = "shelf" | "draft";

const DRAG_MOVIE_MIME = "text/cinema-showcase-movie-id";
const BOARD_START_HOUR = 9;
const BOARD_END_HOUR = 24;
const LAST_SESSION_START_HOUR = 22;
const SLOT_MINUTES = 30;
const PIXELS_PER_MINUTE = 1.8;
const BOARD_WIDTH = (BOARD_END_HOUR - BOARD_START_HOUR) * 60 * PIXELS_PER_MINUTE;

const emptyMovieForm: MovieCreatePayload = {
  title: "",
  description: "",
  duration_minutes: 120,
  genres: [],
  is_active: true,
};

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function toDateKey(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDayLabel(dayKey: string): string {
  const [year, month, day] = dayKey.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });
}

function formatLocalDateTime(value: string): string {
  return new Date(value).toLocaleString([], {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toDateTimeLocal(value: string): string {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function addMinutesToDateTimeLocal(value: string, minutes: number): string {
  if (!value) {
    return value;
  }
  const date = new Date(value);
  date.setMinutes(date.getMinutes() + minutes);
  return toDateTimeLocal(date.toISOString());
}

function getBoardMinuteOffset(date: Date): number {
  return (date.getHours() - BOARD_START_HOUR) * 60 + date.getMinutes();
}

function clampMinutes(value: number): number {
  const max = (BOARD_END_HOUR - BOARD_START_HOUR) * 60;
  return Math.min(Math.max(value, 0), max);
}

function buildDayDate(dayKey: string, hour: number, minute: number): string {
  return `${dayKey}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function getSessionCardStyle(startTime: string, endTime: string): { left: string; width: string } {
  const startDate = new Date(startTime);
  const endDate = new Date(endTime);
  const startOffset = clampMinutes(getBoardMinuteOffset(startDate));
  const durationMinutes = Math.max((endDate.getTime() - startDate.getTime()) / 60000, SLOT_MINUTES);

  return {
    left: `${startOffset * PIXELS_PER_MINUTE}px`,
    width: `${Math.max(durationMinutes * PIXELS_PER_MINUTE, SLOT_MINUTES * PIXELS_PER_MINUTE)}px`,
  };
}

function getDraftDurationMinutes(draft: Pick<SessionDraft, "start_time" | "end_time">): number {
  const startDate = new Date(draft.start_time);
  const endDate = new Date(draft.end_time);

  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return SLOT_MINUTES;
  }

  return Math.max(Math.round((endDate.getTime() - startDate.getTime()) / 60000), SLOT_MINUTES);
}

export function AdminScheduleManagement({
  movies,
  sessions,
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
  const dragActivationFrameRef = useRef<number | null>(null);
  const dragMetaRef = useRef<{ movieId: string; origin: DragOrigin } | null>(null);
  const [movieForm, setMovieForm] = useState<MovieCreatePayload>(emptyMovieForm);
  const [genresInput, setGenresInput] = useState("");
  const [editingMovieId, setEditingMovieId] = useState<string | null>(null);
  const [movieQuery, setMovieQuery] = useState("");
  const [plannerMovieQuery, setPlannerMovieQuery] = useState("");
  const [selectedDay, setSelectedDay] = useState(() => toDateKey(new Date()));
  const [pinnedMovieId, setPinnedMovieId] = useState<string | null>(null);
  const [draggedMovieId, setDraggedMovieId] = useState<string | null>(null);
  const [dragOrigin, setDragOrigin] = useState<DragOrigin | null>(null);
  const [dragPreview, setDragPreview] = useState<DragPreview | null>(null);
  const [draftPlacement, setDraftPlacement] = useState<SessionDraft | null>(null);
  const [editingDraft, setEditingDraft] = useState<SessionEditDraft | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [inspectorView, setInspectorView] = useState<InspectorView>("none");
  const [plannerNotice, setPlannerNotice] = useState<PlannerNotice | null>(null);

  const moviesById = useMemo(
    () =>
      movies.reduce<Record<string, Movie>>((accumulator, movie) => {
        accumulator[movie.id] = movie;
        return accumulator;
      }, {}),
    [movies],
  );

  const sortedMovies = useMemo(
    () => [...movies].sort((left, right) => left.title.localeCompare(right.title)),
    [movies],
  );

  const activeMovies = useMemo(
    () => sortedMovies.filter((movie) => movie.is_active),
    [sortedMovies],
  );

  const catalogMovies = useMemo(() => {
    const normalizedQuery = movieQuery.trim().toLowerCase();
    return sortedMovies.filter((movie) => {
      if (!normalizedQuery) {
        return true;
      }

      const haystack = [
        movie.title,
        movie.description,
        movie.age_rating ?? "",
        movie.genres.join(" "),
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [movieQuery, sortedMovies]);

  const planningMovies = useMemo(() => {
    const normalizedQuery = plannerMovieQuery.trim().toLowerCase();
    return activeMovies.filter((movie) => {
      if (!normalizedQuery) {
        return true;
      }
      return [movie.title, movie.genres.join(" ")].join(" ").toLowerCase().includes(normalizedQuery);
    });
  }, [activeMovies, plannerMovieQuery]);

  const sessionsByMoviePrice = useMemo(() => {
    const map = new Map<string, number>();
    const sortedByNewest = [...sessions].sort(
      (left, right) => new Date(right.start_time).getTime() - new Date(left.start_time).getTime(),
    );

    for (const session of sortedByNewest) {
      if (!map.has(session.movie_id)) {
        map.set(session.movie_id, session.price);
      }
    }

    return map;
  }, [sessions]);

  const selectedDaySessions = useMemo(
    () =>
      [...sessions]
        .filter((session) => toDateKey(session.start_time) === selectedDay)
        .sort((left, right) => new Date(left.start_time).getTime() - new Date(right.start_time).getTime()),
    [selectedDay, sessions],
  );

  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions],
  );

  const selectedMovie = pinnedMovieId ? moviesById[pinnedMovieId] ?? null : null;
  const draggedMovie = draggedMovieId ? moviesById[draggedMovieId] ?? null : null;
  const candidateMovie = draggedMovie ?? selectedMovie;
  const previewMovie = dragPreview ? moviesById[dragPreview.movieId] ?? null : null;
  const draftMovie = draftPlacement ? moviesById[draftPlacement.movie_id] ?? null : null;
  const editingMovie = editingDraft ? moviesById[editingDraft.movie_id] ?? null : null;
  const isDraggingDraft =
    dragOrigin === "draft" &&
    !!draftPlacement &&
    draggedMovieId === draftPlacement.movie_id;
  const candidateDurationMinutes =
    candidateMovie && draftPlacement && candidateMovie.id === draftPlacement.movie_id
      ? getDraftDurationMinutes(draftPlacement)
      : null;

  const movieOptionsForSessionForms = useMemo(
    () =>
      sortedMovies.filter(
        (movie) =>
          movie.is_active ||
          movie.id === draftPlacement?.movie_id ||
          movie.id === editingDraft?.movie_id ||
          movie.id === selectedSession?.movie_id,
      ),
    [draftPlacement?.movie_id, editingDraft?.movie_id, selectedSession?.movie_id, sortedMovies],
  );

  const quickDayOptions = useMemo(() => {
    const counts = sessions.reduce<Map<string, number>>((accumulator, session) => {
      const dayKey = toDateKey(session.start_time);
      accumulator.set(dayKey, (accumulator.get(dayKey) ?? 0) + 1);
      return accumulator;
    }, new Map<string, number>());

    const dayKeys = new Set<string>([selectedDay]);
    for (let index = 0; index < 7; index += 1) {
      const date = new Date();
      date.setDate(date.getDate() + index);
      dayKeys.add(toDateKey(date));
    }
    for (const session of sessions) {
      dayKeys.add(toDateKey(session.start_time));
    }

    return [...dayKeys]
      .sort((left, right) => new Date(left).getTime() - new Date(right).getTime())
      .map((dayKey) => ({
        value: dayKey,
        label: formatDayLabel(dayKey),
        count: counts.get(dayKey) ?? 0,
      }));
  }, [selectedDay, sessions]);

  const boardStats = useMemo(() => {
    const soldTickets = selectedDaySessions.reduce(
      (accumulator, session) => accumulator + (session.total_seats - session.available_seats),
      0,
    );
    const availableSeats = selectedDaySessions.reduce(
      (accumulator, session) => accumulator + session.available_seats,
      0,
    );

    return {
      sessions: selectedDaySessions.length,
      soldTickets,
      availableSeats,
    };
  }, [selectedDaySessions]);

  const nowMarkerOffset = useMemo(() => {
    if (selectedDay !== toDateKey(new Date())) {
      return null;
    }

    const now = new Date();
    const boardOffset = getBoardMinuteOffset(now);
    const maxOffset = (BOARD_END_HOUR - BOARD_START_HOUR) * 60;
    if (boardOffset < 0 || boardOffset > maxOffset) {
      return null;
    }

    return `${boardOffset * PIXELS_PER_MINUTE}px`;
  }, [selectedDay]);

  function getSuggestedEndTime(movieId: string, startTime: string): string {
    const movie = moviesById[movieId];
    if (!movie || !startTime) {
      return startTime;
    }
    return addMinutesToDateTimeLocal(startTime, movie.duration_minutes);
  }

  function getSuggestedPrice(movieId: string): number {
    return sessionsByMoviePrice.get(movieId) ?? 200;
  }

  function getSlotBlockedReason(
    startTime: string,
    movieId: string,
    sessionIdToIgnore?: string,
    durationMinutesOverride?: number,
  ): string | null {
    const movie = moviesById[movieId];
    if (!movie) {
      return "Choose a valid movie before scheduling.";
    }

    const startDate = new Date(startTime);
    if (Number.isNaN(startDate.getTime())) {
      return "Select a valid session start time.";
    }
    if (startDate.getTime() <= Date.now()) {
      return "Sessions must start in the future.";
    }

    const startHour = startDate.getHours();
    const startMinute = startDate.getMinutes();
    if (startHour > LAST_SESSION_START_HOUR || (startHour === LAST_SESSION_START_HOUR && startMinute > 0)) {
      return "New sessions can start no later than 22:00.";
    }

    const proposedDurationMinutes = durationMinutesOverride ?? movie.duration_minutes;
    const proposedEnd = new Date(startDate.getTime() + proposedDurationMinutes * 60_000);
    const blockingSession = selectedDaySessions.find((session) => {
      if (session.id === sessionIdToIgnore || session.status === "cancelled") {
        return false;
      }

      const existingStart = new Date(session.start_time);
      const existingEnd = new Date(session.end_time);
      return startDate < existingEnd && proposedEnd > existingStart;
    });

    if (blockingSession) {
      return `This slot overlaps with "${blockingSession.movie.title}" (${formatTime(blockingSession.start_time)}-${formatTime(blockingSession.end_time)}).`;
    }

    return null;
  }

  const boardSlots = useMemo(() => {
    const slots: Array<{
      key: string;
      startTime: string;
      label: string;
      left: string;
      width: string;
      blockedReason: string | null;
    }> = [];

    const totalMinutes = (BOARD_END_HOUR - BOARD_START_HOUR) * 60;
    for (let offset = 0; offset < totalMinutes; offset += SLOT_MINUTES) {
      const absoluteMinutes = BOARD_START_HOUR * 60 + offset;
      const hour = Math.floor(absoluteMinutes / 60);
      const minute = absoluteMinutes % 60;
      const startTime = buildDayDate(selectedDay, hour, minute);
      const blockedReason = candidateMovie
        ? getSlotBlockedReason(startTime, candidateMovie.id, undefined, candidateDurationMinutes ?? undefined)
        : null;

      slots.push({
        key: `${selectedDay}-${hour}-${minute}`,
        startTime,
        label: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`,
        left: `${offset * PIXELS_PER_MINUTE}px`,
        width: `${SLOT_MINUTES * PIXELS_PER_MINUTE}px`,
        blockedReason,
      });
    }

    return slots;
  }, [candidateDurationMinutes, candidateMovie, selectedDay, selectedDaySessions]);

  useEffect(() => {
    if (pinnedMovieId && !moviesById[pinnedMovieId]) {
      setPinnedMovieId(null);
    }
  }, [moviesById, pinnedMovieId]);

  useEffect(() => {
    if (selectedSessionId && !selectedSession) {
      setSelectedSessionId(null);
      setInspectorView(draftPlacement ? "draft" : "none");
      setEditingDraft(null);
    }
  }, [draftPlacement, selectedSession, selectedSessionId]);

  useEffect(() => {
    if (draftPlacement && !moviesById[draftPlacement.movie_id]) {
      setDraftPlacement(null);
      setInspectorView("none");
    }
  }, [draftPlacement, moviesById]);

  useEffect(() => {
    if (editingDraft && !moviesById[editingDraft.movie_id]) {
      setEditingDraft(null);
      setInspectorView(selectedSession ? "session" : draftPlacement ? "draft" : "none");
    }
  }, [draftPlacement, editingDraft, moviesById, selectedSession]);

  useEffect(
    () => () => {
      if (dragActivationFrameRef.current !== null) {
        window.cancelAnimationFrame(dragActivationFrameRef.current);
      }
    },
    [],
  );

  function resetMovieForm() {
    setMovieForm(emptyMovieForm);
    setGenresInput("");
    setEditingMovieId(null);
  }

  function queueBoardDrag(movieId: string, origin: DragOrigin) {
    dragMetaRef.current = { movieId, origin };
    if (dragActivationFrameRef.current !== null) {
      window.cancelAnimationFrame(dragActivationFrameRef.current);
    }

    dragActivationFrameRef.current = window.requestAnimationFrame(() => {
      setDraggedMovieId(movieId);
      setDragOrigin(origin);
      setDragPreview(null);
      dragActivationFrameRef.current = null;
    });
  }

  function clearBoardDragState() {
    if (dragActivationFrameRef.current !== null) {
      window.cancelAnimationFrame(dragActivationFrameRef.current);
      dragActivationFrameRef.current = null;
    }
    dragMetaRef.current = null;
    setDraggedMovieId(null);
    setDragOrigin(null);
    setDragPreview(null);
  }

  function clearDraftPlacement() {
    setDraftPlacement(null);
    clearPlanningBanners();
    if (inspectorView === "draft") {
      setInspectorView(selectedSession ? "session" : "none");
    }
  }

  function clearPlanningSelection() {
    setPinnedMovieId(null);
    clearBoardDragState();
  }

  function clearPlanningBanners() {
    clearPlanningSelection();
    setPlannerNotice((currentNotice) => (currentNotice?.scope === "planning" ? null : currentNotice));
  }

  function openDraftPlacement(movieId: string, startTime: string, sourceLabel: string) {
    setDraftPlacement({
      movie_id: movieId,
      start_time: startTime,
      end_time: getSuggestedEndTime(movieId, startTime),
      price: getSuggestedPrice(movieId),
      autoFillEndTime: true,
      sourceLabel,
    });
    setEditingDraft(null);
    setSelectedSessionId(null);
    setInspectorView("draft");
    setPinnedMovieId(movieId);
    setSelectedDay(toDateKey(startTime));
  }

  function moveDraftPlacement(startTime: string, sourceLabel: string) {
    if (!draftPlacement) {
      return;
    }

    const movie = moviesById[draftPlacement.movie_id];
    if (!movie) {
      setPlannerNotice({
        scope: "planning",
        tone: "error",
        title: "Draft unavailable",
        message: "The current draft can no longer be moved because its movie is unavailable.",
      });
      return;
    }

    const durationMinutes = getDraftDurationMinutes(draftPlacement);
    const blockedReason = getSlotBlockedReason(startTime, draftPlacement.movie_id, undefined, durationMinutes);
    if (blockedReason) {
      setPlannerNotice({
        scope: "planning",
        tone: "warning",
        title: "Slot unavailable",
        message: blockedReason,
      });
      return;
    }

    setDraftPlacement({
      ...draftPlacement,
      start_time: startTime,
      end_time: addMinutesToDateTimeLocal(startTime, durationMinutes),
      sourceLabel,
    });
    setEditingDraft(null);
    setSelectedSessionId(null);
    setInspectorView("draft");
    setPinnedMovieId(draftPlacement.movie_id);
    setSelectedDay(toDateKey(startTime));
    setDragPreview(null);
    setPlannerNotice({
      scope: "planning",
      tone: "success",
      title: "Draft moved on the board",
      message: `${movie.title} is now staged at ${formatLocalDateTime(startTime)}. It is still only saved after you press Create Session.`,
    });
  }

  function openEditSessionDraft(session: SessionDetails) {
    setEditingDraft({
      sessionId: session.id,
      movie_id: session.movie_id,
      start_time: toDateTimeLocal(session.start_time),
      end_time: toDateTimeLocal(session.end_time),
      price: session.price,
      autoFillEndTime: false,
      sourceLabel: `Editing ${session.movie.title}`,
    });
    setSelectedSessionId(session.id);
    setInspectorView("edit");
    setPlannerNotice(null);
  }

  function handleMovieCatalogEdit(movie: Movie) {
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
  }

  function handlePlanningMovieSelect(movie: Movie) {
    setPinnedMovieId(movie.id);
    setPlannerNotice({
      scope: "planning",
      tone: "info",
      title: "Movie ready for planning",
      message: `Drag "${movie.title}" onto the timeline, or click a free slot to start a draft.`,
    });
  }

  function handleSlotPlacement(movieId: string, startTime: string, sourceLabel: string) {
    const movie = moviesById[movieId];
    if (!movie) {
      setPlannerNotice({
        scope: "planning",
        tone: "error",
        title: "Movie unavailable",
        message: "The selected movie is no longer available for scheduling.",
      });
      return;
    }

    const blockedReason = getSlotBlockedReason(startTime, movieId);
    if (blockedReason) {
      setPlannerNotice({
        scope: "planning",
        tone: "warning",
        title: "Slot unavailable",
        message: blockedReason,
      });
      return;
    }

    openDraftPlacement(movieId, startTime, sourceLabel);
    setDragPreview(null);
    setPlannerNotice({
      scope: "planning",
      tone: "success",
      title: "Draft placed on the board",
      message: `${movie.title} is now staged at ${formatLocalDateTime(startTime)}. It will only be saved after you press Create Session.`,
    });
  }

  function getDragPreviewEndTime(movieId: string, startTime: string): string {
    if (dragOrigin === "draft" && draftPlacement && draftPlacement.movie_id === movieId) {
      return addMinutesToDateTimeLocal(startTime, getDraftDurationMinutes(draftPlacement));
    }

    return getSuggestedEndTime(movieId, startTime);
  }

  async function handleMovieSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedPayload: MovieCreatePayload = {
      ...movieForm,
      title: movieForm.title.trim(),
      description: movieForm.description.trim(),
      poster_url: movieForm.poster_url?.trim() || undefined,
      age_rating: movieForm.age_rating?.trim() || undefined,
      genres: genresInput
        .split(",")
        .map((genre) => genre.trim())
        .filter(Boolean),
    };

    if (editingMovieId) {
      const updatedMovie = await onUpdateMovie(editingMovieId, normalizedPayload as MovieUpdatePayload);
      if (!updatedMovie) {
        return;
      }
      resetMovieForm();
      return;
    }

    const createdMovie = await onCreateMovie(normalizedPayload);
    if (!createdMovie) {
      return;
    }
    resetMovieForm();
    setPinnedMovieId(createdMovie.id);
  }

  async function handleDeactivateMovie(movie: Movie) {
    const confirmed = window.confirm(
      `Deactivate "${movie.title}"? Existing sessions and ticket history will stay intact.`,
    );
    if (!confirmed) {
      return;
    }

    const result = await onDeactivateMovie(movie.id);
    if (!result) {
      return;
    }

    if (pinnedMovieId === movie.id) {
      setPinnedMovieId(null);
    }
  }

  async function handleDeleteMovie(movie: Movie) {
    const confirmed = window.confirm(
      `Delete "${movie.title}"? This only succeeds when no sessions reference it.`,
    );
    if (!confirmed) {
      return;
    }

    const result = await onDeleteMovie(movie.id);
    if (!result) {
      return;
    }

    if (editingMovieId === movie.id) {
      resetMovieForm();
    }
    if (pinnedMovieId === movie.id) {
      setPinnedMovieId(null);
    }
  }

  function updateDraftField<K extends keyof SessionDraft>(field: K, value: SessionDraft[K]) {
    setDraftPlacement((currentDraft) => {
      if (!currentDraft) {
        return currentDraft;
      }

      const nextDraft = { ...currentDraft, [field]: value };
      if (field === "end_time") {
        nextDraft.autoFillEndTime = false;
        return nextDraft;
      }

      if ((field === "movie_id" || field === "start_time") && nextDraft.autoFillEndTime) {
        nextDraft.end_time = getSuggestedEndTime(nextDraft.movie_id, nextDraft.start_time);
      }

      return nextDraft;
    });
  }

  function updateEditingDraftField<K extends keyof SessionEditDraft>(field: K, value: SessionEditDraft[K]) {
    setEditingDraft((currentDraft) => {
      if (!currentDraft) {
        return currentDraft;
      }

      const nextDraft = { ...currentDraft, [field]: value };
      if (field === "end_time") {
        nextDraft.autoFillEndTime = false;
        return nextDraft;
      }

      if ((field === "movie_id" || field === "start_time") && nextDraft.autoFillEndTime) {
        nextDraft.end_time = getSuggestedEndTime(nextDraft.movie_id, nextDraft.start_time);
      }

      return nextDraft;
    });
  }

  async function handleCreateDraftSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draftPlacement) {
      return;
    }

    const createdSession = await onCreateSession({
      movie_id: draftPlacement.movie_id,
      start_time: draftPlacement.start_time,
      end_time: draftPlacement.end_time,
      price: Number(draftPlacement.price),
    });
    if (!createdSession) {
      return;
    }

    setDraftPlacement(null);
    clearPlanningBanners();
    setSelectedSessionId(createdSession.id);
    setInspectorView("session");
    setSelectedDay(toDateKey(createdSession.start_time));
    setPlannerNotice({
      scope: "session",
      tone: "success",
      title: "Session created",
      message: `${createdSession.movie.title} is now confirmed on the board at ${formatTime(createdSession.start_time)}-${formatTime(createdSession.end_time)}.`,
    });
  }

  async function handleUpdateEditedSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingDraft) {
      return;
    }

    const updatedSession = await onUpdateSession(editingDraft.sessionId, {
      movie_id: editingDraft.movie_id,
      start_time: editingDraft.start_time,
      end_time: editingDraft.end_time,
      price: Number(editingDraft.price),
    });
    if (!updatedSession) {
      return;
    }

    setEditingDraft(null);
    setSelectedSessionId(updatedSession.id);
    setInspectorView("session");
    setSelectedDay(toDateKey(updatedSession.start_time));
    setPlannerNotice({
      scope: "session",
      tone: "success",
      title: "Session updated",
      message: `${updatedSession.movie.title} now runs at ${formatTime(updatedSession.start_time)}-${formatTime(updatedSession.end_time)}.`,
    });
  }

  async function handleCancelSelectedSession() {
    if (!selectedSession) {
      return;
    }

    const confirmed = window.confirm(`Cancel the session for "${selectedSession.movie.title}"?`);
    if (!confirmed) {
      return;
    }

    const result = await onCancelSession(selectedSession.id);
    if (!result) {
      return;
    }

    setInspectorView("session");
    setPlannerNotice({
      scope: "session",
      tone: "success",
      title: "Session cancelled",
      message: `The session remains on the board for ${formatDayLabel(selectedDay)} with a cancelled status.`,
    });
  }

  async function handleDeleteSelectedSession() {
    if (!selectedSession) {
      return;
    }

    const confirmed = window.confirm(`Delete the session for "${selectedSession.movie.title}"?`);
    if (!confirmed) {
      return;
    }

    const result = await onDeleteSession(selectedSession.id);
    if (!result) {
      return;
    }

    setSelectedSessionId(null);
    setEditingDraft(null);
    setInspectorView(draftPlacement ? "draft" : "none");
    setPlannerNotice({
      scope: "session",
      tone: "success",
      title: "Session deleted",
      message: "The time slot is open again and ready for a new draft placement.",
    });
  }

  const visibleDraft = draftPlacement && toDateKey(draftPlacement.start_time) === selectedDay ? draftPlacement : null;
  const previewEndTime = dragPreview ? getDragPreviewEndTime(dragPreview.movieId, dragPreview.startTime) : null;
  const previewDurationMinutes =
    dragPreview && dragOrigin === "draft" && draftPlacement && draftPlacement.movie_id === dragPreview.movieId
      ? getDraftDurationMinutes(draftPlacement)
      : previewMovie?.duration_minutes ?? null;

  return (
    <section className="admin-stack">
      <section className="form-card admin-zone">
        <div className="admin-section__header">
          <div>
            <p className="page-eyebrow">Movie Management</p>
            <h2 className="section-title">Maintain the movie catalog</h2>
            <p className="muted">
              Build the lineup here first. Active titles become available in the planning shelf.
            </p>
          </div>
          <div className="stats-row">
            <span className="badge">{activeMovies.length} active titles</span>
            <span className="badge">{movies.length} total titles</span>
          </div>
        </div>

        <div className="admin-zone__layout">
          <form className="admin-form admin-zone__form" onSubmit={(event) => void handleMovieSubmit(event)}>
            <div className="admin-section__header">
              <div>
                <p className="page-eyebrow">{editingMovieId ? "Editing movie" : "New movie"}</p>
                <h3 className="section-title">
                  {editingMovieId ? "Update movie details" : "Add a title to the catalog"}
                </h3>
              </div>
              {editingMovieId ? (
                <button className="button--ghost" type="button" disabled={isBusy} onClick={resetMovieForm}>
                  Clear form
                </button>
              ) : null}
            </div>

            {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

            <div className="form-grid">
              <label className="field">
                <span>Title</span>
                <input required disabled={isBusy} value={movieForm.title} onChange={(event) => setMovieForm((current) => ({ ...current, title: event.target.value }))} />
              </label>
              <label className="field">
                <span>Duration, min</span>
                <input required min={1} max={600} type="number" disabled={isBusy} value={movieForm.duration_minutes} onChange={(event) => setMovieForm((current) => ({ ...current, duration_minutes: Number(event.target.value) }))} />
              </label>
              <label className="field field--wide">
                <span>Description</span>
                <textarea required disabled={isBusy} value={movieForm.description} onChange={(event) => setMovieForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <label className="field">
                <span>Age rating</span>
                <input disabled={isBusy} value={movieForm.age_rating ?? ""} onChange={(event) => setMovieForm((current) => ({ ...current, age_rating: event.target.value || undefined }))} />
              </label>
              <label className="field">
                <span>Poster URL</span>
                <input type="url" disabled={isBusy} value={movieForm.poster_url ?? ""} onChange={(event) => setMovieForm((current) => ({ ...current, poster_url: event.target.value || undefined }))} />
              </label>
              <label className="field field--wide">
                <span>Genres</span>
                <input disabled={isBusy} value={genresInput} onChange={(event) => setGenresInput(event.target.value)} placeholder="Drama, Comedy, Thriller" />
              </label>
              <label className="field field--checkbox">
                <input checked={movieForm.is_active} type="checkbox" disabled={isBusy} onChange={(event) => setMovieForm((current) => ({ ...current, is_active: event.target.checked }))} />
                <span>Keep this title active for scheduling</span>
              </label>
            </div>

            <div className="actions-row">
              <button className="button" type="submit" disabled={isBusy}>
                {isBusy ? "Saving..." : editingMovieId ? "Save movie changes" : "Create movie"}
              </button>
            </div>
          </form>

          <section className="admin-zone__catalog">
            <div className="admin-section__header">
              <div>
                <p className="page-eyebrow">Catalog</p>
                <h3 className="section-title">Current lineup</h3>
              </div>
              <span className="badge">{catalogMovies.length}</span>
            </div>

            <label className="field">
              <span>Filter movies</span>
              <input value={movieQuery} onChange={(event) => setMovieQuery(event.target.value)} placeholder="Search by title, genre, rating, or description" />
            </label>

            <div className="admin-catalog__list">
              {catalogMovies.map((movie) => (
                <article key={movie.id} className="card admin-catalog__card">
                  <div className="admin-card__header">
                    <div className="admin-catalog__media">
                      <div className="media-tile" aria-hidden="true">
                        {movie.poster_url ? <img src={movie.poster_url} alt="" className="media-tile__image" /> : <span>{getMovieMonogram(movie.title)}</span>}
                      </div>
                      <div className="admin-catalog__copy">
                        <strong>{movie.title}</strong>
                        <p className="muted">{movie.description}</p>
                      </div>
                    </div>
                    <div className="stats-row">
                      <span className="badge">{movie.duration_minutes} min</span>
                      <span className={`badge${movie.is_active ? "" : " badge--danger"}`}>{movie.is_active ? "Active" : "Inactive"}</span>
                    </div>
                  </div>

                  <div className="stats-row">
                    {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                    {movie.genres.length > 0 ? <span className="badge">{movie.genres.join(", ")}</span> : null}
                  </div>

                  <div className="actions-row">
                    <button className="button--ghost" type="button" disabled={isBusy} onClick={() => handleMovieCatalogEdit(movie)}>Edit movie</button>
                    <button className="button--ghost" type="button" disabled={isBusy || !movie.is_active} onClick={() => handlePlanningMovieSelect(movie)}>Queue for board</button>
                    <button className="button--ghost" type="button" disabled={isBusy || !movie.is_active} onClick={() => void handleDeactivateMovie(movie)}>Deactivate</button>
                    <button className="button--danger" type="button" disabled={isBusy} onClick={() => void handleDeleteMovie(movie)}>Delete movie</button>
                  </div>
                </article>
              ))}

              {catalogMovies.length === 0 ? (
                <section className="empty-state empty-state--panel">
                  <h2>No movies found</h2>
                  <p>Adjust the filter or create a new movie to begin scheduling.</p>
                </section>
              ) : null}
            </div>
          </section>
        </div>
      </section>

      <section className="form-card admin-zone">
        <div className="admin-board-context">
          <div className="admin-board-context__hero">
            <div className="admin-board-context__copy">
              <p className="admin-board-context__eyebrow">Board For</p>
              <h2 className="admin-board-context__title">{formatDayLabel(selectedDay)}</h2>
              <p className="admin-board-context__subtitle">
                One hall, one timeline. Stage drafts on the board first, then confirm them from the inspector.
              </p>
            </div>
            <div className="admin-board-context__controls">
              <label className="field">
                <span>Board date</span>
                <input type="date" value={selectedDay} onChange={(event) => setSelectedDay(event.target.value)} />
              </label>
              <div className="actions-row">
                <button className="button--ghost" type="button" onClick={() => setSelectedDay(toDateKey(new Date()))}>Today</button>
                {draftPlacement ? (
                  <button className="button--ghost" type="button" onClick={clearDraftPlacement}>Discard draft</button>
                ) : null}
              </div>
            </div>
          </div>

          <div className="stats-row">
            <span className="badge">{boardStats.sessions} sessions</span>
            <span className="badge">{boardStats.soldTickets} tickets sold</span>
            <span className="badge">{boardStats.availableSeats} seats open</span>
            {draftPlacement ? <span className="badge">1 draft pending</span> : null}
          </div>

          <div className="day-pills">
            {quickDayOptions.map((option) => (
              <button key={option.value} type="button" className={`day-pill${option.value === selectedDay ? " is-active" : ""}`} onClick={() => setSelectedDay(option.value)}>
                <strong>{option.label}</strong>
                <span>{option.count} sessions</span>
              </button>
            ))}
          </div>
        </div>

        {plannerNotice ? (
          <StatusBanner
            tone={plannerNotice.tone}
            title={plannerNotice.title}
            message={plannerNotice.message}
            action={<button className="button--ghost" type="button" onClick={() => setPlannerNotice(null)}>Dismiss</button>}
          />
        ) : null}

        <section className="card chrono-stage">
          <div className="admin-section__header">
            <div>
              <p className="page-eyebrow">Timeline</p>
              <h3 className="section-title">Drag to place, then confirm</h3>
              <p className="muted">Gray blocks are drafts or previews. Only saved sessions use the normal session styling.</p>
            </div>
            <div className="stats-row">
              {candidateMovie ? <span className="badge">{candidateMovie.title}</span> : <span className="badge">Select a movie to plan</span>}
            </div>
          </div>

          <div className="chrono-stage__frame">
            <div className="chrono-board" style={{ width: `${BOARD_WIDTH}px` }}>
              <div className="chrono-board__scale">
                {Array.from({ length: BOARD_END_HOUR - BOARD_START_HOUR + 1 }, (_, index) => {
                  const hour = BOARD_START_HOUR + index;
                  const label = `${String(hour).padStart(2, "0")}:00`;
                  const left = `${(hour - BOARD_START_HOUR) * 60 * PIXELS_PER_MINUTE}px`;
                  return <div key={label} className="chrono-board__hour-label" style={{ left }}>{label}</div>;
                })}
              </div>

              <div
                className={`chrono-board__lane${draggedMovieId ? " is-dragging" : ""}`}
                onDragLeave={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setDragPreview(null);
                  }
                }}
              >
                {Array.from({ length: BOARD_END_HOUR - BOARD_START_HOUR + 1 }, (_, index) => {
                  const left = `${index * 60 * PIXELS_PER_MINUTE}px`;
                  return <div key={left} className="chrono-board__hour-line" style={{ left }} />;
                })}

                {boardSlots.map((slot) => (
                  <button
                    key={slot.key}
                    type="button"
                    className={[
                      "chrono-board__slot",
                      candidateMovie && !slot.blockedReason ? "is-available" : "",
                      candidateMovie && slot.blockedReason ? "is-blocked" : "",
                    ].filter(Boolean).join(" ")}
                    style={{ left: slot.left, width: slot.width }}
                    onClick={() => {
                      if (!selectedMovie) {
                        setPlannerNotice({
                          scope: "planning",
                          tone: "info",
                          title: "Select a movie first",
                          message: "Choose a movie from the Planning Shelf, then click a free slot on the board.",
                        });
                        return;
                      }
                      if (draftPlacement && draftPlacement.movie_id === selectedMovie.id) {
                        moveDraftPlacement(slot.startTime, "Draft moved from a board click");
                        return;
                      }
                      handleSlotPlacement(selectedMovie.id, slot.startTime, "Draft placed from a board click");
                    }}
                    onDragOver={(event) => {
                      const activeDraggedMovieId = draggedMovieId ?? dragMetaRef.current?.movieId ?? null;
                      const activeDragOrigin = dragOrigin ?? dragMetaRef.current?.origin ?? null;
                      if (!activeDraggedMovieId) {
                        return;
                      }
                      event.preventDefault();
                      event.dataTransfer.dropEffect = slot.blockedReason ? "none" : activeDragOrigin === "draft" ? "move" : "copy";
                      setDragPreview(slot.blockedReason ? null : { movieId: activeDraggedMovieId, startTime: slot.startTime });
                    }}
                    onDrop={(event) => {
                      event.preventDefault();
                      const activeDrag = dragMetaRef.current
                        ?? (draggedMovieId && dragOrigin ? { movieId: draggedMovieId, origin: dragOrigin } : null);
                      const movieId =
                        event.dataTransfer.getData(DRAG_MOVIE_MIME)
                        || event.dataTransfer.getData("text/plain")
                        || activeDrag?.movieId;
                      if (!movieId) {
                        return;
                      }
                      const currentDragOrigin = activeDrag?.origin ?? null;
                      clearBoardDragState();
                      if (currentDragOrigin === "draft" && draftPlacement?.movie_id === movieId) {
                        moveDraftPlacement(slot.startTime, "Draft moved from drag and drop");
                        return;
                      }
                      handleSlotPlacement(movieId, slot.startTime, "Draft placed from drag and drop");
                    }}
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
                      <strong title={previewMovie.title}>{previewMovie.title}</strong>
                      <span className="badge">Preview</span>
                    </div>
                    <p className="chrono-session__time">{formatTime(dragPreview.startTime)} - {formatTime(previewEndTime)}</p>
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
                    ].filter(Boolean).join(" ")}
                    style={getSessionCardStyle(visibleDraft.start_time, visibleDraft.end_time)}
                    draggable={!isBusy}
                    onDragStart={(event) => {
                      event.dataTransfer.setData(DRAG_MOVIE_MIME, visibleDraft.movie_id);
                      event.dataTransfer.setData("text/plain", visibleDraft.movie_id);
                      event.dataTransfer.effectAllowed = "move";
                      queueBoardDrag(visibleDraft.movie_id, "draft");
                    }}
                    onDragEnd={clearBoardDragState}
                    onClick={() => {
                      setSelectedSessionId(null);
                      setEditingDraft(null);
                      setInspectorView("draft");
                    }}
                  >
                    <div className="chrono-session__header">
                      <strong title={draftMovie.title}>{draftMovie.title}</strong>
                      <span className="badge">Draft</span>
                    </div>
                    <p className="chrono-session__time">{formatTime(visibleDraft.start_time)} - {formatTime(visibleDraft.end_time)}</p>
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
                      onClick={() => {
                        setSelectedSessionId(session.id);
                        setEditingDraft(null);
                        setInspectorView("session");
                        setPinnedMovieId(session.movie_id);
                        setPlannerNotice(null);
                      }}
                    >
                      <div className="chrono-session__header">
                        <strong title={session.movie.title}>{session.movie.title}</strong>
                        <span className="badge">{formatStateLabel(session.status)}</span>
                      </div>
                      <p className="chrono-session__time">{formatTime(session.start_time)} - {formatTime(session.end_time)}</p>
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

        <div className="chrono-workbench">
          <section className="card planning-shelf">
            <div className="admin-section__header">
              <div>
                <p className="page-eyebrow">Planning Shelf</p>
                <h3 className="section-title">Drag source / staging area</h3>
                <p className="muted">Pick an active title, then drag it onto the board to create a gray draft.</p>
              </div>
              <span className="badge">{planningMovies.length}</span>
            </div>

            <label className="field">
              <span>Find an active movie</span>
              <input value={plannerMovieQuery} onChange={(event) => setPlannerMovieQuery(event.target.value)} placeholder="Search active titles" />
            </label>

            {selectedMovie ? (
              <StatusBanner
                tone="info"
                title="Selected movie"
                message={`${selectedMovie.title} is queued for board placement. Drag it or click a free slot on the timeline.`}
                action={<button className="button--ghost" type="button" onClick={clearPlanningSelection}>Clear</button>}
              />
            ) : null}

            <div className="planning-shelf__grid">
              {planningMovies.map((movie) => {
                const isSelected = movie.id === pinnedMovieId || movie.id === draggedMovieId;

                return (
                  <article
                    key={movie.id}
                    className={`admin-source-card${isSelected ? " is-selected" : ""}`}
                    draggable={!isBusy}
                    onDragStart={(event) => {
                      event.dataTransfer.setData(DRAG_MOVIE_MIME, movie.id);
                      event.dataTransfer.setData("text/plain", movie.id);
                      event.dataTransfer.effectAllowed = "copy";
                      queueBoardDrag(movie.id, "shelf");
                    }}
                    onDragEnd={clearBoardDragState}
                  >
                    <div className="admin-source-card__header">
                      <div className="media-tile admin-source-card__media" aria-hidden="true">
                        {movie.poster_url ? <img src={movie.poster_url} alt="" className="media-tile__image" /> : <span>{getMovieMonogram(movie.title)}</span>}
                      </div>
                      <div>
                        <strong>{movie.title}</strong>
                        <p className="muted">{movie.duration_minutes} min</p>
                      </div>
                    </div>
                    <div className="stats-row">
                      {movie.age_rating ? <span className="badge">{movie.age_rating}</span> : null}
                      {movie.genres.length > 0 ? <span className="badge">{movie.genres.join(", ")}</span> : null}
                    </div>
                    <div className="actions-row">
                      <button className="button--ghost" type="button" disabled={isBusy} onClick={() => handlePlanningMovieSelect(movie)}>Select</button>
                    </div>
                  </article>
                );
              })}

              {planningMovies.length === 0 ? (
                <section className="empty-state empty-state--panel">
                  <h2>No active movies ready</h2>
                  <p>Activate or create a movie first, then drag it from the shelf onto the board.</p>
                </section>
              ) : null}
            </div>
          </section>

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
                <button className="button--ghost" type="button" onClick={clearDraftPlacement}>Discard draft</button>
              ) : null}
            </div>

            {busyActionLabel ? <p className="muted">{busyActionLabel}...</p> : null}

            {inspectorView === "draft" && draftPlacement ? (
              <form className="admin-planner__form" onSubmit={(event) => void handleCreateDraftSession(event)}>
                <p className="muted">{draftPlacement.sourceLabel}</p>
                <div className="form-grid">
                  <label className="field field--wide">
                    <span>Movie</span>
                    <select required disabled={isBusy} value={draftPlacement.movie_id} onChange={(event) => updateDraftField("movie_id", event.target.value)}>
                      <option value="">Select a movie</option>
                      {movieOptionsForSessionForms.map((movie) => <option key={movie.id} value={movie.id}>{movie.title}</option>)}
                    </select>
                  </label>
                  <label className="field">
                    <span>Planned start</span>
                    <input required type="datetime-local" disabled={isBusy} value={draftPlacement.start_time} onChange={(event) => updateDraftField("start_time", event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Calculated end</span>
                    <input required type="datetime-local" disabled={isBusy} value={draftPlacement.end_time} onChange={(event) => updateDraftField("end_time", event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Price</span>
                    <input required min={0} type="number" disabled={isBusy} value={draftPlacement.price} onChange={(event) => updateDraftField("price", Number(event.target.value))} />
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
                  <button className="button--ghost" type="button" disabled={isBusy} onClick={() => setDraftPlacement((currentDraft) => currentDraft ? { ...currentDraft, autoFillEndTime: true, end_time: getSuggestedEndTime(currentDraft.movie_id, currentDraft.start_time) } : currentDraft)}>
                    Reset to the recommended end time
                  </button>
                ) : null}

                <div className="actions-row">
                  <button className="button" type="submit" disabled={isBusy}>Create Session</button>
                </div>
              </form>
            ) : null}

            {inspectorView === "edit" && editingDraft ? (
              <form className="admin-planner__form" onSubmit={(event) => void handleUpdateEditedSession(event)}>
                <p className="muted">{editingDraft.sourceLabel}</p>
                <div className="form-grid">
                  <label className="field field--wide">
                    <span>Movie</span>
                    <select required disabled={isBusy} value={editingDraft.movie_id} onChange={(event) => updateEditingDraftField("movie_id", event.target.value)}>
                      <option value="">Select a movie</option>
                      {movieOptionsForSessionForms.map((movie) => <option key={movie.id} value={movie.id}>{movie.title}</option>)}
                    </select>
                  </label>
                  <label className="field">
                    <span>Starts at</span>
                    <input required type="datetime-local" disabled={isBusy} value={editingDraft.start_time} onChange={(event) => updateEditingDraftField("start_time", event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Ends at</span>
                    <input required type="datetime-local" disabled={isBusy} value={editingDraft.end_time} onChange={(event) => updateEditingDraftField("end_time", event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Price</span>
                    <input required min={0} type="number" disabled={isBusy} value={editingDraft.price} onChange={(event) => updateEditingDraftField("price", Number(event.target.value))} />
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
                  <button className="button" type="submit" disabled={isBusy}>Save session changes</button>
                  <button className="button--ghost" type="button" disabled={isBusy} onClick={() => setInspectorView("session")}>Back to session</button>
                </div>
              </form>
            ) : null}

            {inspectorView === "session" && selectedSession ? (
              <div className="inspector-panel__details">
                <div className="inspector-panel__poster-row">
                  <div className="media-tile inspector-panel__poster" aria-hidden="true">
                    {selectedSession.movie.poster_url ? <img src={selectedSession.movie.poster_url} alt="" className="media-tile__image" /> : <span>{getMovieMonogram(selectedSession.movie.title)}</span>}
                  </div>
                  <div>
                    <strong>{selectedSession.movie.title}</strong>
                    <p className="muted">{formatDateTime(selectedSession.start_time)} to {formatTime(selectedSession.end_time)}</p>
                  </div>
                </div>

                <div className="stats-row">
                  <span className="badge">{formatStateLabel(selectedSession.status)}</span>
                  <span className="badge">{formatCurrency(selectedSession.price)}</span>
                  <span className="badge">{selectedSession.total_seats - selectedSession.available_seats} sold</span>
                  <span className="badge">{selectedSession.available_seats}/{selectedSession.total_seats} left</span>
                </div>

                <p className="muted">{selectedSession.movie.description}</p>

                <div className="stats-row">
                  {selectedSession.movie.age_rating ? <span className="badge">{selectedSession.movie.age_rating}</span> : null}
                  {selectedSession.movie.genres.length > 0 ? <span className="badge">{selectedSession.movie.genres.join(", ")}</span> : null}
                </div>

                <div className="actions-row">
                  <button className="button--ghost" type="button" disabled={isBusy} onClick={() => openEditSessionDraft(selectedSession)}>Edit session</button>
                  <button className="button--ghost" type="button" disabled={isBusy || selectedSession.status !== "scheduled"} onClick={() => void handleCancelSelectedSession()}>Cancel session</button>
                  <button className="button--danger" type="button" disabled={isBusy} onClick={() => void handleDeleteSelectedSession()}>Delete session</button>
                </div>
              </div>
            ) : null}

            {inspectorView === "none" ? (
              <StatePanel
                title="Use the inspector as the control center"
                message="Drag a movie from the Planning Shelf onto the board to stage a gray draft, or select an existing session card to inspect it."
                action={<button className="button--ghost" type="button" onClick={() => setSelectedDay(toDateKey(new Date()))}>Jump to today</button>}
              />
            ) : null}
          </section>
        </div>
      </section>
    </section>
  );
}
