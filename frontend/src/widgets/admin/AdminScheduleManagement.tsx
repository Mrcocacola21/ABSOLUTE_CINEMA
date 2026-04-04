import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  MovieCreatePayload,
  MovieUpdatePayload,
  SessionBatchCreatePayload,
  SessionBatchCreateResult,
  SessionCreatePayload,
  SessionUpdatePayload,
} from "@/api/admin";
import { buildGenreSearchText } from "@/shared/genres";
import {
  buildLocalizedSearchText,
  compareLocalizedText,
  getLocalizedText,
} from "@/shared/localization";
import { isMovieScheduleReady } from "@/shared/movieStatus";
import type { Movie, Session, SessionDetails } from "@/types/domain";
import { ChronoboardHeader } from "@/widgets/admin/chronoboard/ChronoboardHeader";
import { ChronoboardInspector } from "@/widgets/admin/chronoboard/ChronoboardInspector";
import { ChronoboardTimeline } from "@/widgets/admin/chronoboard/ChronoboardTimeline";
import { MovieCatalogPanel } from "@/widgets/admin/chronoboard/MovieCatalogPanel";
import { PlanningShelf } from "@/widgets/admin/chronoboard/PlanningShelf";
import { useChronoboardState } from "@/widgets/admin/chronoboard/useChronoboardState";

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
  onCreateSessionsBatch: (payload: SessionBatchCreatePayload) => Promise<SessionBatchCreateResult | null>;
  onUpdateSession: (sessionId: string, payload: SessionUpdatePayload) => Promise<SessionDetails | null>;
  onCancelSession: (sessionId: string) => Promise<Session | null>;
  onDeleteSession: (sessionId: string) => Promise<{ id: string; deleted: boolean } | null>;
}

const emptyMovieForm: MovieCreatePayload = {
  title: {
    uk: "",
    en: "",
  },
  description: {
    uk: "",
    en: "",
  },
  duration_minutes: 120,
  genres: [],
  status: "planned",
};

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
  onCreateSessionsBatch,
  onUpdateSession,
  onCancelSession,
  onDeleteSession,
}: AdminScheduleManagementProps) {
  const { t, i18n } = useTranslation();
  const [movieForm, setMovieForm] = useState<MovieCreatePayload>(emptyMovieForm);
  const [editingMovieId, setEditingMovieId] = useState<string | null>(null);
  const [movieQuery, setMovieQuery] = useState("");

  const moviesById = useMemo(
    () =>
      movies.reduce<Record<string, Movie>>((accumulator, movie) => {
        accumulator[movie.id] = movie;
        return accumulator;
      }, {}),
    [movies],
  );

  const sortedMovies = useMemo(
    () => [...movies].sort((left, right) => compareLocalizedText(left.title, right.title, i18n.language)),
    [i18n.language, movies],
  );

  const scheduleReadyMovies = useMemo(
    () => sortedMovies.filter((movie) => isMovieScheduleReady(movie)),
    [sortedMovies],
  );

  const statusCounts = useMemo(
    () => ({
      planned: sortedMovies.filter((movie) => movie.status === "planned").length,
      active: sortedMovies.filter((movie) => movie.status === "active").length,
      deactivated: sortedMovies.filter((movie) => movie.status === "deactivated").length,
    }),
    [sortedMovies],
  );

  const catalogMovies = useMemo(() => {
    const normalizedQuery = movieQuery.trim().toLowerCase();
    return sortedMovies.filter((movie) => {
      if (!normalizedQuery) {
        return true;
      }

      const haystack = [
        buildLocalizedSearchText(movie.title),
        buildLocalizedSearchText(movie.description),
        movie.age_rating ?? "",
        movie.genres.map((genre) => buildGenreSearchText(genre)).join(" "),
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    });
  }, [movieQuery, sortedMovies]);

  const chronoboard = useChronoboardState({
    language: i18n.language,
    moviesById,
    sortedMovies,
    scheduleReadyMovies,
    sessions,
    onCreateSession,
    onCreateSessionsBatch,
    onUpdateSession,
    onCancelSession,
    onDeleteSession,
  });

  function updateMovieFormField<K extends keyof MovieCreatePayload>(field: K, value: MovieCreatePayload[K]) {
    setMovieForm((current) => ({ ...current, [field]: value }));
  }

  function updateLocalizedMovieFormField(
    field: "title" | "description",
    locale: "uk" | "en",
    value: string,
  ) {
    setMovieForm((current) => ({
      ...current,
      [field]: {
        ...current[field],
        [locale]: value,
      },
    }));
  }

  function toggleMovieGenre(genre: MovieCreatePayload["genres"][number]) {
    setMovieForm((current) => ({
      ...current,
      genres: current.genres.includes(genre)
        ? current.genres.filter((currentGenre) => currentGenre !== genre)
        : [...current.genres, genre],
    }));
  }

  function resetMovieForm() {
    setMovieForm(emptyMovieForm);
    setEditingMovieId(null);
  }

  function handleMovieCatalogEdit(movie: Movie) {
    setEditingMovieId(movie.id);
    setMovieForm({
      title: { ...movie.title },
      description: { ...movie.description },
      duration_minutes: movie.duration_minutes,
      poster_url: movie.poster_url ?? undefined,
      age_rating: movie.age_rating ?? undefined,
      genres: [...movie.genres],
      status: movie.status,
    });
  }

  async function handleMovieSubmit() {
    const normalizedPayload: MovieCreatePayload = {
      ...movieForm,
      title: {
        uk: movieForm.title.uk.trim(),
        en: movieForm.title.en.trim(),
      },
      description: {
        uk: movieForm.description.uk.trim(),
        en: movieForm.description.en.trim(),
      },
      poster_url: movieForm.poster_url?.trim() || undefined,
      age_rating: movieForm.age_rating?.trim() || undefined,
      genres: [...new Set(movieForm.genres)],
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
    if (isMovieScheduleReady(createdMovie)) {
      chronoboard.pinMovie(createdMovie.id);
    }
  }

  async function handleDeactivateManagedMovie(movie: Movie) {
    const movieLabel = getLocalizedText(movie.title, i18n.language);
    const confirmed = window.confirm(t("admin.confirmations.deactivateMovie", { movie: movieLabel }));
    if (!confirmed) {
      return;
    }

    const result = await onDeactivateMovie(movie.id);
    if (!result) {
      return;
    }

    if (chronoboard.pinnedMovieId === movie.id) {
      chronoboard.clearPlanningSelection();
    }
  }

  async function handleReturnMovieToPlanned(movie: Movie) {
    const movieLabel = getLocalizedText(movie.title, i18n.language);
    const confirmed = window.confirm(t("admin.confirmations.returnMovie", { movie: movieLabel }));
    if (!confirmed) {
      return;
    }

    const result = await onUpdateMovie(movie.id, { status: "planned" });
    if (!result) {
      return;
    }
  }

  async function handleDeleteManagedMovie(movie: Movie) {
    const movieLabel = getLocalizedText(movie.title, i18n.language);
    const confirmed = window.confirm(t("admin.confirmations.deleteMovie", { movie: movieLabel }));
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
    if (chronoboard.pinnedMovieId === movie.id) {
      chronoboard.clearPlanningSelection();
    }
  }

  return (
    <section className="admin-stack">
      <MovieCatalogPanel
        catalogMovies={catalogMovies}
        totalMoviesCount={movies.length}
        scheduleReadyMoviesCount={scheduleReadyMovies.length}
        statusCounts={statusCounts}
        isBusy={isBusy}
        busyActionLabel={busyActionLabel}
        movieForm={movieForm}
        editingMovieId={editingMovieId}
        movieQuery={movieQuery}
        onMovieFormChange={updateMovieFormField}
        onLocalizedMovieFormChange={updateLocalizedMovieFormField}
        onToggleGenre={toggleMovieGenre}
        onMovieQueryChange={setMovieQuery}
        onSubmit={handleMovieSubmit}
        onResetForm={resetMovieForm}
        onEditMovie={handleMovieCatalogEdit}
        onQueueMovie={chronoboard.handlePlanningMovieSelect}
        onDeactivateMovie={handleDeactivateManagedMovie}
        onReturnToPlanned={handleReturnMovieToPlanned}
        onDeleteMovie={handleDeleteManagedMovie}
      />

      <section className="form-card admin-zone">
        <ChronoboardHeader
          selectedDay={chronoboard.selectedDay}
          quickDayOptions={chronoboard.quickDayOptions}
          boardStats={chronoboard.boardStats}
          hasDraft={Boolean(chronoboard.draftPlacement)}
          plannerNotice={chronoboard.plannerNotice}
          onSelectedDayChange={chronoboard.setSelectedDay}
          onJumpToToday={chronoboard.jumpToToday}
          onDiscardDraft={chronoboard.clearDraftPlacement}
          onDismissNotice={chronoboard.dismissPlannerNotice}
        />

        <ChronoboardTimeline
          candidateMovie={chronoboard.candidateMovie}
          draggedMovieId={chronoboard.draggedMovieId}
          boardSlots={chronoboard.boardSlots}
          nowMarkerOffset={chronoboard.nowMarkerOffset}
          previewMovie={chronoboard.previewMovie}
          dragPreview={chronoboard.dragPreview}
          previewEndTime={chronoboard.previewEndTime}
          previewDurationMinutes={chronoboard.previewDurationMinutes}
          highlightedConflictSessionId={chronoboard.highlightedConflictSessionId}
          dragOrigin={chronoboard.dragOrigin}
          visibleDraft={chronoboard.visibleDraft}
          draftMovie={chronoboard.draftMovie}
          inspectorView={chronoboard.inspectorView}
          isDraggingDraft={chronoboard.isDraggingDraft}
          selectedDaySessions={chronoboard.selectedDaySessions}
          selectedSessionId={chronoboard.selectedSessionId}
          isBusy={isBusy}
          onLaneDragLeave={chronoboard.handleBoardLaneDragLeave}
          onSlotClick={chronoboard.handleBoardSlotClick}
          onSlotDragOver={chronoboard.handleBoardSlotDragOver}
          onSlotDrop={chronoboard.handleBoardSlotDrop}
          onDraftDragStart={chronoboard.handleDraftDragStart}
          onDragEnd={chronoboard.handleDragEnd}
          onDraftSelect={chronoboard.handleDraftSelect}
          onSessionSelect={chronoboard.handleSessionSelect}
        />

        <div className="chrono-workbench">
          <PlanningShelf
            planningMovies={chronoboard.planningMovies}
            plannerMovieQuery={chronoboard.plannerMovieQuery}
            selectedMovie={chronoboard.selectedMovie}
            pinnedMovieId={chronoboard.pinnedMovieId}
            draggedMovieId={chronoboard.draggedMovieId}
            isBusy={isBusy}
            onPlannerMovieQueryChange={chronoboard.setPlannerMovieQuery}
            onSelectMovie={chronoboard.handlePlanningMovieSelect}
            onClearPlanningSelection={chronoboard.clearPlanningSelection}
            onDragStart={chronoboard.handleShelfDragStart}
            onDragEnd={chronoboard.handleDragEnd}
          />

          <ChronoboardInspector
            inspectorView={chronoboard.inspectorView}
            draftPlacement={chronoboard.draftPlacement}
            draftDatePlans={chronoboard.draftDatePlans}
            draftSelectionSummary={chronoboard.draftSelectionSummary}
            draftWeekdayLabels={chronoboard.draftWeekdayLabels}
            draftCalendarMonthLabel={chronoboard.draftCalendarMonthLabel}
            draftCalendarDays={chronoboard.draftCalendarDays}
            editingDraft={chronoboard.editingDraft}
            selectedSession={chronoboard.selectedSession}
            draftMovie={chronoboard.draftMovie}
            editingMovie={chronoboard.editingMovie}
            movieOptionsForSessionForms={chronoboard.movieOptionsForSessionForms}
            isBusy={isBusy}
            busyActionLabel={busyActionLabel}
            onDiscardDraft={chronoboard.clearDraftPlacement}
            onToggleDraftDate={chronoboard.toggleDraftDate}
            onShowPreviousDraftMonth={chronoboard.showPreviousDraftMonth}
            onShowNextDraftMonth={chronoboard.showNextDraftMonth}
            onUpdateDraftField={chronoboard.updateDraftField}
            onUpdateEditingDraftField={chronoboard.updateEditingDraftField}
            onResetDraftEndTime={chronoboard.resetDraftEndTime}
            onCreateDraftSession={chronoboard.handleCreateDraftSession}
            onUpdateEditedSession={chronoboard.handleUpdateEditedSession}
            onBackToSession={chronoboard.backToSession}
            onOpenEditSessionDraft={chronoboard.openEditSessionDraft}
            onOpenDuplicateSessionDraft={chronoboard.openDuplicateSessionDraft}
            onCancelSelectedSession={chronoboard.handleCancelSelectedSession}
            onDeleteSelectedSession={chronoboard.handleDeleteSelectedSession}
            onJumpToToday={chronoboard.jumpToToday}
          />
        </div>
      </section>
    </section>
  );
}
