import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";

import type {
  SessionBatchCreatePayload,
  SessionBatchCreateResult,
  SessionCreatePayload,
  SessionUpdatePayload,
} from "@/api/admin";
import { buildGenreSearchText } from "@/shared/genres";
import { buildLocalizedSearchText, getLocalizedText } from "@/shared/localization";
import { isMovieScheduleReady } from "@/shared/movieStatus";
import { formatTime } from "@/shared/presentation";
import type { Movie, Session, SessionDetails } from "@/types/domain";
import type {
  BoardSlot,
  DraftCalendarDay,
  DraftDatePlan,
  DragOrigin,
  DragPreview,
  InspectorView,
  PlannerNotice,
  SessionDraft,
  SessionEditDraft,
} from "@/widgets/admin/chronoboard/types";
import {
  BOARD_START_HOUR,
  BOARD_TOTAL_MINUTES,
  DRAG_MOVIE_MIME,
  LAST_SESSION_START_HOUR,
  PIXELS_PER_MINUTE,
  SLOT_MINUTES,
  addMinutesToDateTimeLocal,
  buildCalendarDays,
  buildCalendarWeekdayLabels,
  buildDayDate,
  combineDateKeyAndTime,
  formatDayLabel,
  formatDayPillLabel,
  formatLocalDateTime,
  formatMonthLabel,
  getBoardMinuteOffset,
  getDraftDurationMinutes,
  shiftMonthKey,
  toDateKey,
  toMonthKey,
  toDateTimeLocal,
  sortDateKeys,
} from "@/widgets/admin/chronoboard/utils";

interface UseChronoboardStateOptions {
  language: string;
  moviesById: Record<string, Movie>;
  sortedMovies: Movie[];
  scheduleReadyMovies: Movie[];
  sessions: SessionDetails[];
  onCreateSession: (payload: SessionCreatePayload) => Promise<SessionDetails | null>;
  onCreateSessionsBatch: (payload: SessionBatchCreatePayload) => Promise<SessionBatchCreateResult | null>;
  onUpdateSession: (sessionId: string, payload: SessionUpdatePayload) => Promise<SessionDetails | null>;
  onCancelSession: (sessionId: string) => Promise<Session | null>;
  onDeleteSession: (sessionId: string) => Promise<{ id: string; deleted: boolean } | null>;
}

export function useChronoboardState({
  language,
  moviesById,
  sortedMovies,
  scheduleReadyMovies,
  sessions,
  onCreateSession,
  onCreateSessionsBatch,
  onUpdateSession,
  onCancelSession,
  onDeleteSession,
}: UseChronoboardStateOptions) {
  const { t } = useTranslation();
  const dragActivationFrameRef = useRef<number | null>(null);
  const dragMetaRef = useRef<{ movieId: string; origin: DragOrigin } | null>(null);
  const [plannerMovieQuery, setPlannerMovieQuery] = useState("");
  const [selectedDay, setSelectedDay] = useState(() => toDateKey(new Date()));
  const [pinnedMovieId, setPinnedMovieId] = useState<string | null>(null);
  const [draggedMovieId, setDraggedMovieId] = useState<string | null>(null);
  const [dragOrigin, setDragOrigin] = useState<DragOrigin | null>(null);
  const [dragPreview, setDragPreview] = useState<DragPreview | null>(null);
  const [highlightedConflictSessionId, setHighlightedConflictSessionId] = useState<string | null>(null);
  const [draftPlacement, setDraftPlacement] = useState<SessionDraft | null>(null);
  const [editingDraft, setEditingDraft] = useState<SessionEditDraft | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [inspectorView, setInspectorView] = useState<InspectorView>("none");
  const [plannerNotice, setPlannerNotice] = useState<PlannerNotice | null>(null);

  function getMovieLabel(movie: Pick<Movie, "title">): string {
    return getLocalizedText(movie.title, language);
  }

  const planningMovies = useMemo(() => {
    const normalizedQuery = plannerMovieQuery.trim().toLowerCase();
    return scheduleReadyMovies.filter((movie) => {
      if (!normalizedQuery) {
        return true;
      }

      return [buildLocalizedSearchText(movie.title), movie.genres.map((genre) => buildGenreSearchText(genre)).join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    });
  }, [language, plannerMovieQuery, scheduleReadyMovies]);

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
    Boolean(draftPlacement) &&
    draggedMovieId === draftPlacement?.movie_id;
  const candidateDurationMinutes =
    candidateMovie && draftPlacement && candidateMovie.id === draftPlacement.movie_id
      ? getDraftDurationMinutes(draftPlacement)
      : null;

  const movieOptionsForSessionForms = useMemo(
    () =>
      sortedMovies.filter(
        (movie) =>
          isMovieScheduleReady(movie) ||
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

    const boardOffset = getBoardMinuteOffset(new Date());
    if (boardOffset < 0 || boardOffset > BOARD_TOTAL_MINUTES) {
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

  function getDraftPrimaryDateKey(draft: SessionDraft): string {
    return toDateKey(draft.start_time);
  }

  function getDraftTargetDateKeys(draft: SessionDraft): string[] {
    const dateKeys =
      draft.sourceMode === "timeline"
        ? [getDraftPrimaryDateKey(draft), ...draft.extraDateKeys]
        : [...draft.extraDateKeys];
    return sortDateKeys([...new Set(dateKeys)]);
  }

  function buildDraftWindowForDate(
    draft: Pick<SessionDraft, "start_time" | "end_time">,
    dateKey: string,
  ): { startTime: string; endTime: string } {
    const startTime = combineDateKeyAndTime(dateKey, draft.start_time);
    return {
      startTime,
      endTime: addMinutesToDateTimeLocal(startTime, getDraftDurationMinutes(draft)),
    };
  }

  function getSlotConflict(
    startTime: string,
    movieId: string,
    sessionIdToIgnore?: string,
    durationMinutesOverride?: number,
    sessionPool: SessionDetails[] = sessions,
  ): { reason: string | null; blockingSessionId: string | null } {
    const movie = moviesById[movieId];
    if (!movie) {
      return {
        reason: t("chronoboard.notices.chooseValidMovie"),
        blockingSessionId: null,
      };
    }

    const startDate = new Date(startTime);
    if (Number.isNaN(startDate.getTime())) {
      return {
        reason: t("chronoboard.notices.selectValidStart"),
        blockingSessionId: null,
      };
    }
    if (startDate.getTime() <= Date.now()) {
      return {
        reason: t("chronoboard.notices.sessionsFutureOnly"),
        blockingSessionId: null,
      };
    }

    const startHour = startDate.getHours();
    const startMinute = startDate.getMinutes();
    if (startHour > LAST_SESSION_START_HOUR || (startHour === LAST_SESSION_START_HOUR && startMinute > 0)) {
      return {
        reason: t("chronoboard.notices.latestStartTime"),
        blockingSessionId: null,
      };
    }

    const proposedDurationMinutes = durationMinutesOverride ?? movie.duration_minutes;
    const proposedEnd = new Date(startDate.getTime() + proposedDurationMinutes * 60_000);
    const blockingSession = sessionPool.find((session) => {
      if (session.id === sessionIdToIgnore || session.status === "cancelled") {
        return false;
      }

      const existingStart = new Date(session.start_time);
      const existingEnd = new Date(session.end_time);
      return startDate < existingEnd && proposedEnd > existingStart;
    });

    if (blockingSession) {
      return {
        reason: t("chronoboard.notices.overlapMessage", {
          movie: getMovieLabel(blockingSession.movie),
          timeRange: `${formatTime(blockingSession.start_time)}-${formatTime(blockingSession.end_time)}`,
        }),
        blockingSessionId: blockingSession.id,
      };
    }

    return {
      reason: null,
      blockingSessionId: null,
    };
  }

  function getSlotBlockedReason(
    startTime: string,
    movieId: string,
    sessionIdToIgnore?: string,
    durationMinutesOverride?: number,
    sessionPool: SessionDetails[] = sessions,
  ): string | null {
    return getSlotConflict(startTime, movieId, sessionIdToIgnore, durationMinutesOverride, sessionPool).reason;
  }

  const boardSlots = useMemo<BoardSlot[]>(() => {
    const slots: BoardSlot[] = [];

    for (let offset = 0; offset < BOARD_TOTAL_MINUTES; offset += SLOT_MINUTES) {
      const absoluteMinutes = BOARD_START_HOUR * 60 + offset;
      const hour = Math.floor(absoluteMinutes / 60);
      const minute = absoluteMinutes % 60;
      const startTime = buildDayDate(selectedDay, hour, minute);
      const slotConflict = candidateMovie
        ? getSlotConflict(startTime, candidateMovie.id, undefined, candidateDurationMinutes ?? undefined)
        : null;

      slots.push({
        key: `${selectedDay}-${hour}-${minute}`,
        startTime,
        label: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`,
        left: `${offset * PIXELS_PER_MINUTE}px`,
        width: `${SLOT_MINUTES * PIXELS_PER_MINUTE}px`,
        blockedReason: slotConflict?.reason ?? null,
        blockingSessionId: slotConflict?.blockingSessionId ?? null,
      });
    }

    return slots;
  }, [candidateDurationMinutes, candidateMovie, selectedDay, sessions, t]);

  const sessionCountsByDate = useMemo(
    () =>
      sessions.reduce<Map<string, number>>((accumulator, session) => {
        const dateKey = toDateKey(session.start_time);
        accumulator.set(dateKey, (accumulator.get(dateKey) ?? 0) + 1);
        return accumulator;
      }, new Map<string, number>()),
    [sessions],
  );

  const draftDatePlans = useMemo<DraftDatePlan[]>(() => {
    if (!draftPlacement) {
      return [];
    }

    return getDraftTargetDateKeys(draftPlacement).map((dateKey) => {
      const { startTime, endTime } = buildDraftWindowForDate(draftPlacement, dateKey);
      const conflictReason = getSlotBlockedReason(
        startTime,
        draftPlacement.movie_id,
        undefined,
        getDraftDurationMinutes(draftPlacement),
      );

      return {
        dateKey,
        label: formatDayLabel(dateKey),
        shortLabel: formatDayPillLabel(dateKey),
        startTime,
        endTime,
        isLocked: draftPlacement.sourceMode === "timeline" && dateKey === getDraftPrimaryDateKey(draftPlacement),
        isConflicting: Boolean(conflictReason),
        conflictReason,
      };
    });
  }, [draftPlacement, sessions, t]);

  const draftSelectionSummary = useMemo(
    () => ({
      selectedCount: draftDatePlans.length,
      readyCount: draftDatePlans.filter((plan) => !plan.isConflicting).length,
      conflictCount: draftDatePlans.filter((plan) => plan.isConflicting).length,
    }),
    [draftDatePlans],
  );

  const draftWeekdayLabels = useMemo(() => buildCalendarWeekdayLabels(), []);

  const draftCalendarMonthLabel = useMemo(
    () => (draftPlacement ? formatMonthLabel(draftPlacement.calendarMonth) : ""),
    [draftPlacement],
  );

  const draftCalendarDays = useMemo<DraftCalendarDay[]>(() => {
    if (!draftPlacement) {
      return [];
    }

    const selectedDateKeys = new Set(getDraftTargetDateKeys(draftPlacement));
    const conflictingDateKeys = new Set(
      draftDatePlans.filter((plan) => plan.isConflicting).map((plan) => plan.dateKey),
    );
    const primaryDateKey = getDraftPrimaryDateKey(draftPlacement);
    const todayKey = toDateKey(new Date());

    return buildCalendarDays(draftPlacement.calendarMonth).map((day) => {
      const isLocked = draftPlacement.sourceMode === "timeline" && day.dateKey === primaryDateKey;
      const hasSessions = sessionCountsByDate.get(day.dateKey) !== undefined;
      const isPast = new Date(combineDateKeyAndTime(day.dateKey, draftPlacement.start_time)).getTime() <= Date.now();

      return {
        ...day,
        isToday: day.dateKey === todayKey,
        isSelected: selectedDateKeys.has(day.dateKey),
        isLocked,
        isPast,
        hasConflict: conflictingDateKeys.has(day.dateKey),
        hasSessions,
      };
    });
  }, [draftDatePlans, draftPlacement, sessionCountsByDate]);

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
    setHighlightedConflictSessionId(null);
  }

  function clearPlanningSelection() {
    setPinnedMovieId(null);
    clearBoardDragState();
  }

  function clearPlanningBanners() {
    clearPlanningSelection();
    setPlannerNotice((currentNotice) => (currentNotice?.scope === "planning" ? null : currentNotice));
  }

  function openDraftPlacement(
    movieId: string,
    startTime: string,
    sourceLabel: string,
    sourceMode: SessionDraft["sourceMode"] = "timeline",
  ) {
    setDraftPlacement({
      movie_id: movieId,
      start_time: startTime,
      end_time: getSuggestedEndTime(movieId, startTime),
      price: getSuggestedPrice(movieId),
      autoFillEndTime: true,
      sourceLabel,
      sourceMode,
      extraDateKeys: [],
      calendarMonth: toMonthKey(startTime),
    });
    setEditingDraft(null);
    if (sourceMode === "timeline") {
      setSelectedSessionId(null);
    }
    setInspectorView("draft");
    setPinnedMovieId(movieId);
    setSelectedDay(toDateKey(startTime));
    setHighlightedConflictSessionId(null);
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
        title: t("chronoboard.notices.draftUnavailableTitle"),
        message: t("chronoboard.notices.draftUnavailableMessage"),
      });
      return;
    }

    const durationMinutes = getDraftDurationMinutes(draftPlacement);
    const blockedReason = getSlotBlockedReason(startTime, draftPlacement.movie_id, undefined, durationMinutes);
    if (blockedReason) {
      setPlannerNotice({
        scope: "planning",
        tone: "warning",
        title: t("chronoboard.notices.slotUnavailableTitle"),
        message: blockedReason,
      });
      return;
    }

    setDraftPlacement({
      ...draftPlacement,
      start_time: startTime,
      end_time: addMinutesToDateTimeLocal(startTime, durationMinutes),
      sourceLabel,
      extraDateKeys: draftPlacement.extraDateKeys.filter((dateKey) => dateKey !== toDateKey(startTime)),
      calendarMonth: toMonthKey(startTime),
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
      title: t("chronoboard.notices.draftMovedTitle"),
      message: t("chronoboard.notices.draftMovedMessage", {
        movie: getMovieLabel(movie),
        time: formatLocalDateTime(startTime),
      }),
    });
  }

  function handlePlanningMovieSelect(movie: Movie) {
    setPinnedMovieId(movie.id);
    setPlannerNotice({
      scope: "planning",
      tone: "info",
      title: t("chronoboard.notices.movieReadyTitle"),
      message: t("chronoboard.notices.movieReadyMessage", {
        movie: getMovieLabel(movie),
      }),
    });
  }

  function handleSlotPlacement(movieId: string, startTime: string, sourceLabel: string) {
    const movie = moviesById[movieId];
    if (!movie) {
      setPlannerNotice({
        scope: "planning",
        tone: "error",
        title: t("chronoboard.notices.movieUnavailableTitle"),
        message: t("chronoboard.notices.movieUnavailableMessage"),
      });
      return;
    }

    const blockedReason = getSlotBlockedReason(startTime, movieId);
    if (blockedReason) {
      setPlannerNotice({
        scope: "planning",
        tone: "warning",
        title: t("chronoboard.notices.slotUnavailableTitle"),
        message: blockedReason,
      });
      return;
    }

    openDraftPlacement(movieId, startTime, sourceLabel);
    setDragPreview(null);
    setPlannerNotice({
      scope: "planning",
      tone: "success",
      title: t("chronoboard.notices.draftPlacedTitle"),
      message: t("chronoboard.notices.draftPlacedMessage", {
        movie: getMovieLabel(movie),
        time: formatLocalDateTime(startTime),
      }),
    });
  }

  function getDragPreviewEndTime(movieId: string, startTime: string): string {
    if (dragOrigin === "draft" && draftPlacement && draftPlacement.movie_id === movieId) {
      return addMinutesToDateTimeLocal(startTime, getDraftDurationMinutes(draftPlacement));
    }

    return getSuggestedEndTime(movieId, startTime);
  }

  function clearDraftPlacement() {
    setDraftPlacement(null);
    clearPlanningBanners();
    if (inspectorView === "draft") {
      setInspectorView(selectedSession ? "session" : "none");
    }
  }

  function pinMovie(movieId: string | null) {
    setPinnedMovieId(movieId);
  }

  function jumpToToday() {
    setSelectedDay(toDateKey(new Date()));
  }

  function dismissPlannerNotice() {
    setPlannerNotice(null);
  }

  function handleBoardLaneDragLeave(event: DragEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setDragPreview(null);
      setHighlightedConflictSessionId(null);
    }
  }

  function handleBoardSlotClick(startTime: string) {
    if (!selectedMovie) {
      setPlannerNotice({
        scope: "planning",
        tone: "info",
        title: t("chronoboard.notices.selectMovieFirstTitle"),
        message: t("chronoboard.notices.selectMovieFirstMessage"),
      });
      return;
    }

    if (draftPlacement && draftPlacement.sourceMode === "timeline" && draftPlacement.movie_id === selectedMovie.id) {
      moveDraftPlacement(startTime, t("chronoboard.inspector.draftSource.boardMove"));
      return;
    }

    handleSlotPlacement(selectedMovie.id, startTime, t("chronoboard.inspector.draftSource.boardClick"));
  }

  function handleBoardSlotDragOver(event: DragEvent<HTMLButtonElement>, slot: BoardSlot) {
    const activeDraggedMovieId = draggedMovieId ?? dragMetaRef.current?.movieId ?? null;
    const activeDragOrigin = dragOrigin ?? dragMetaRef.current?.origin ?? null;
    if (!activeDraggedMovieId) {
      return;
    }

    event.preventDefault();
    event.dataTransfer.dropEffect = slot.blockedReason
      ? "none"
      : activeDragOrigin === "draft"
        ? "move"
        : "copy";
    setHighlightedConflictSessionId(slot.blockingSessionId);
    setDragPreview(slot.blockedReason ? null : { movieId: activeDraggedMovieId, startTime: slot.startTime });
  }

  function handleBoardSlotDrop(event: DragEvent<HTMLButtonElement>, slot: BoardSlot) {
    event.preventDefault();

    const activeDrag =
      dragMetaRef.current ??
      (draggedMovieId && dragOrigin ? { movieId: draggedMovieId, origin: dragOrigin } : null);
    const movieId =
      event.dataTransfer.getData(DRAG_MOVIE_MIME) ||
      event.dataTransfer.getData("text/plain") ||
      activeDrag?.movieId;

    if (!movieId) {
      return;
    }

    const currentDragOrigin = activeDrag?.origin ?? null;
    clearBoardDragState();
    if (currentDragOrigin === "draft" && draftPlacement?.sourceMode === "timeline" && draftPlacement.movie_id === movieId) {
      moveDraftPlacement(slot.startTime, t("chronoboard.inspector.draftSource.dragMove"));
      return;
    }

    handleSlotPlacement(movieId, slot.startTime, t("chronoboard.inspector.draftSource.dragDrop"));
  }

  function handleShelfDragStart(event: DragEvent<HTMLElement>, movieId: string) {
    event.dataTransfer.setData(DRAG_MOVIE_MIME, movieId);
    event.dataTransfer.setData("text/plain", movieId);
    event.dataTransfer.effectAllowed = "copy";
    queueBoardDrag(movieId, "shelf");
  }

  function handleDraftDragStart(event: DragEvent<HTMLButtonElement>) {
    if (!draftPlacement || draftPlacement.sourceMode !== "timeline") {
      return;
    }

    event.dataTransfer.setData(DRAG_MOVIE_MIME, draftPlacement.movie_id);
    event.dataTransfer.setData("text/plain", draftPlacement.movie_id);
    event.dataTransfer.effectAllowed = "move";
    queueBoardDrag(draftPlacement.movie_id, "draft");
  }

  function handleDraftSelect() {
    setSelectedSessionId(null);
    setEditingDraft(null);
    setInspectorView("draft");
  }

  function toggleDraftDate(dateKey: string) {
    setDraftPlacement((currentDraft) => {
      if (!currentDraft) {
        return currentDraft;
      }

      const primaryDateKey = getDraftPrimaryDateKey(currentDraft);
      if (currentDraft.sourceMode === "timeline" && dateKey === primaryDateKey) {
        return currentDraft;
      }

      const nextExtraDateKeys = currentDraft.extraDateKeys.includes(dateKey)
        ? currentDraft.extraDateKeys.filter((currentDateKey) => currentDateKey !== dateKey)
        : sortDateKeys([...currentDraft.extraDateKeys, dateKey]);

      return {
        ...currentDraft,
        extraDateKeys: nextExtraDateKeys,
      };
    });
  }

  function showPreviousDraftMonth() {
    setDraftPlacement((currentDraft) =>
      currentDraft
        ? {
            ...currentDraft,
            calendarMonth: shiftMonthKey(currentDraft.calendarMonth, -1),
          }
        : currentDraft,
    );
  }

  function showNextDraftMonth() {
    setDraftPlacement((currentDraft) =>
      currentDraft
        ? {
            ...currentDraft,
            calendarMonth: shiftMonthKey(currentDraft.calendarMonth, 1),
          }
        : currentDraft,
    );
  }

  function handleSessionSelect(session: SessionDetails) {
    setSelectedSessionId(session.id);
    setEditingDraft(null);
    setInspectorView("session");
    setPlannerNotice(null);
  }

  function openEditSessionDraft(session: SessionDetails) {
    setEditingDraft({
      sessionId: session.id,
      movie_id: session.movie_id,
      start_time: toDateTimeLocal(session.start_time),
      end_time: toDateTimeLocal(session.end_time),
      price: session.price,
      autoFillEndTime: false,
      sourceLabel: t("chronoboard.inspector.draftSource.editingSaved", {
        movie: getMovieLabel(session.movie),
      }),
    });
    setSelectedSessionId(session.id);
    setInspectorView("edit");
    setPlannerNotice(null);
  }

  function openDuplicateSessionDraft(session: SessionDetails) {
    setDraftPlacement({
      movie_id: session.movie_id,
      start_time: toDateTimeLocal(session.start_time),
      end_time: toDateTimeLocal(session.end_time),
      price: session.price,
      autoFillEndTime: false,
      sourceLabel: t("chronoboard.inspector.draftSource.duplicatingSaved", {
        movie: getMovieLabel(session.movie),
      }),
      sourceMode: "duplicate",
      extraDateKeys: [],
      calendarMonth: toMonthKey(session.start_time),
    });
    setEditingDraft(null);
    setInspectorView("draft");
    setPlannerNotice({
      scope: "session",
      tone: "info",
      title: t("chronoboard.notices.duplicateReadyTitle"),
      message: t("chronoboard.notices.duplicateReadyMessage", {
        movie: getMovieLabel(session.movie),
        timeRange: `${formatTime(session.start_time)}-${formatTime(session.end_time)}`,
      }),
    });
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

      if (field === "start_time") {
        nextDraft.extraDateKeys = nextDraft.extraDateKeys.filter(
          (dateKey) => dateKey !== getDraftPrimaryDateKey(nextDraft),
        );
        nextDraft.calendarMonth = toMonthKey(nextDraft.start_time);
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

  function resetDraftEndTime() {
    setDraftPlacement((currentDraft) =>
      currentDraft
        ? {
            ...currentDraft,
            autoFillEndTime: true,
            end_time: getSuggestedEndTime(currentDraft.movie_id, currentDraft.start_time),
          }
        : currentDraft,
    );
  }

  async function handleCreateDraftSession() {
    if (!draftPlacement) {
      return;
    }

    const targetDateKeys = getDraftTargetDateKeys(draftPlacement);
    if (targetDateKeys.length === 0) {
      setPlannerNotice({
        scope: "session",
        tone: "warning",
        title: t("chronoboard.notices.chooseDatesTitle"),
        message: t("chronoboard.notices.chooseDatesMessage"),
      });
      return;
    }

    if (draftDatePlans.every((plan) => plan.isConflicting)) {
      setPlannerNotice({
        scope: "session",
        tone: "warning",
        title: t("chronoboard.notices.allSelectedDatesBlockedTitle"),
        message: t("chronoboard.notices.allSelectedDatesBlockedMessage"),
      });
      return;
    }

    const shouldCreateSingleSession = draftPlacement.sourceMode === "timeline" && targetDateKeys.length === 1;
    if (shouldCreateSingleSession) {
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
        title: t("chronoboard.notices.sessionCreatedTitle"),
        message: t("chronoboard.notices.sessionCreatedMessage", {
          movie: getMovieLabel(createdSession.movie),
          timeRange: `${formatTime(createdSession.start_time)}-${formatTime(createdSession.end_time)}`,
        }),
      });
      return;
    }

    const batchResult = await onCreateSessionsBatch({
      movie_id: draftPlacement.movie_id,
      start_time: draftPlacement.start_time,
      end_time: draftPlacement.end_time,
      price: Number(draftPlacement.price),
      dates: targetDateKeys,
    });
    if (!batchResult) {
      return;
    }

    const firstCreatedSession = batchResult.created_sessions[0] ?? null;
    const rejectedDateKeys = sortDateKeys(batchResult.rejected_dates.map((item) => item.date));

    if (batchResult.rejected_count === 0) {
      setDraftPlacement(null);
      if (draftPlacement.sourceMode === "timeline") {
        clearPlanningBanners();
      }

      if (draftPlacement.sourceMode === "duplicate") {
        setInspectorView(selectedSession ? "session" : "none");
      } else if (firstCreatedSession) {
        setSelectedSessionId(firstCreatedSession.id);
        setInspectorView("session");
        setSelectedDay(toDateKey(firstCreatedSession.start_time));
      }

      setPlannerNotice({
        scope: "session",
        tone: "success",
        title: t("chronoboard.notices.batchCreatedTitle", { count: batchResult.created_count }),
        message: t("chronoboard.notices.batchCreatedMessage", {
          count: batchResult.created_count,
          movie: draftMovie ? getMovieLabel(draftMovie) : "",
          timeRange:
            firstCreatedSession !== null
              ? `${formatTime(firstCreatedSession.start_time)}-${formatTime(firstCreatedSession.end_time)}`
              : `${formatTime(draftPlacement.start_time)}-${formatTime(draftPlacement.end_time)}`,
        }),
      });
      return;
    }

    setDraftPlacement((currentDraft) => {
      if (!currentDraft) {
        return currentDraft;
      }

      const primaryDateKey = getDraftPrimaryDateKey(currentDraft);
      const shouldRemainTimelineDraft =
        currentDraft.sourceMode === "timeline" && rejectedDateKeys.includes(primaryDateKey);

      return {
        ...currentDraft,
        sourceMode: shouldRemainTimelineDraft ? "timeline" : "duplicate",
        extraDateKeys: shouldRemainTimelineDraft
          ? rejectedDateKeys.filter((dateKey) => dateKey !== primaryDateKey)
          : rejectedDateKeys,
        calendarMonth: toMonthKey(rejectedDateKeys[0] ?? currentDraft.start_time),
      };
    });
    setInspectorView("draft");
    setPlannerNotice({
      scope: "session",
      tone: "warning",
      title: t("chronoboard.notices.batchCreatedPartialTitle", {
        createdCount: batchResult.created_count,
        rejectedCount: batchResult.rejected_count,
      }),
      message: t("chronoboard.notices.batchCreatedPartialMessage", {
        createdCount: batchResult.created_count,
        rejectedCount: batchResult.rejected_count,
      }),
    });
  }

  async function handleUpdateEditedSession() {
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
      title: t("chronoboard.notices.sessionUpdatedTitle"),
      message: t("chronoboard.notices.sessionUpdatedMessage", {
        movie: getMovieLabel(updatedSession.movie),
        timeRange: `${formatTime(updatedSession.start_time)}-${formatTime(updatedSession.end_time)}`,
      }),
    });
  }

  async function handleCancelSelectedSession() {
    if (!selectedSession) {
      return;
    }

    const confirmed = window.confirm(
      t("chronoboard.confirmations.cancelSession", {
        movie: getMovieLabel(selectedSession.movie),
      }),
    );
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
      title: t("chronoboard.notices.sessionCancelledTitle"),
      message: t("chronoboard.notices.sessionCancelledMessage", {
        day: formatDayLabel(selectedDay),
      }),
    });
  }

  async function handleDeleteSelectedSession() {
    if (!selectedSession) {
      return;
    }

    const confirmed = window.confirm(
      t("chronoboard.confirmations.deleteSession", {
        movie: getMovieLabel(selectedSession.movie),
      }),
    );
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
      title: t("chronoboard.notices.sessionDeletedTitle"),
      message: t("chronoboard.notices.sessionDeletedMessage"),
    });
  }

  const visibleDraft =
    draftPlacement && draftPlacement.sourceMode === "timeline" && toDateKey(draftPlacement.start_time) === selectedDay
      ? draftPlacement
      : null;
  const previewEndTime = dragPreview ? getDragPreviewEndTime(dragPreview.movieId, dragPreview.startTime) : null;
  const previewDurationMinutes =
    dragPreview && dragOrigin === "draft" && draftPlacement && draftPlacement.movie_id === dragPreview.movieId
      ? getDraftDurationMinutes(draftPlacement)
      : previewMovie?.duration_minutes ?? null;

  function backToSession() {
    setInspectorView("session");
  }

  return {
    selectedDay,
    plannerMovieQuery,
    planningMovies,
    selectedMovie,
    pinnedMovieId,
    draggedMovieId,
    plannerNotice,
    draftPlacement,
    draftDatePlans,
    draftSelectionSummary,
    draftWeekdayLabels,
    draftCalendarMonthLabel,
    draftCalendarDays,
    editingDraft,
    selectedSession,
    selectedSessionId,
    inspectorView,
    movieOptionsForSessionForms,
    draftMovie,
    editingMovie,
    quickDayOptions,
    boardStats,
    candidateMovie,
    boardSlots,
    nowMarkerOffset,
    previewMovie,
    dragPreview,
    highlightedConflictSessionId,
    previewEndTime,
    previewDurationMinutes,
    dragOrigin,
    visibleDraft,
    isDraggingDraft,
    selectedDaySessions,
    setSelectedDay,
    setPlannerMovieQuery,
    pinMovie,
    jumpToToday,
    dismissPlannerNotice,
    clearPlanningSelection,
    clearDraftPlacement,
    handlePlanningMovieSelect,
    handleBoardLaneDragLeave,
    handleBoardSlotClick,
    handleBoardSlotDragOver,
    handleBoardSlotDrop,
    handleShelfDragStart,
    handleDraftDragStart,
    handleDragEnd: clearBoardDragState,
    handleDraftSelect,
    toggleDraftDate,
    showPreviousDraftMonth,
    showNextDraftMonth,
    handleSessionSelect,
    openEditSessionDraft,
    openDuplicateSessionDraft,
    updateDraftField,
    updateEditingDraftField,
    resetDraftEndTime,
    handleCreateDraftSession,
    handleUpdateEditedSession,
    handleCancelSelectedSession,
    handleDeleteSelectedSession,
    backToSession,
  };
}
