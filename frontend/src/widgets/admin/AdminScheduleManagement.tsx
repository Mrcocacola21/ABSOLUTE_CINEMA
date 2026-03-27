import { useMemo, useState } from "react";

import type {
  MovieCreatePayload,
  MovieUpdatePayload,
  SessionCreatePayload,
  SessionUpdatePayload,
} from "@/api/admin";
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
  onUpdateSession: (sessionId: string, payload: SessionUpdatePayload) => Promise<SessionDetails | null>;
  onCancelSession: (sessionId: string) => Promise<Session | null>;
  onDeleteSession: (sessionId: string) => Promise<{ id: string; deleted: boolean } | null>;
}

const emptyMovieForm: MovieCreatePayload = {
  title: "",
  description: "",
  duration_minutes: 120,
  genres: [],
  is_active: true,
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
  onUpdateSession,
  onCancelSession,
  onDeleteSession,
}: AdminScheduleManagementProps) {
  const [movieForm, setMovieForm] = useState<MovieCreatePayload>(emptyMovieForm);
  const [genresInput, setGenresInput] = useState("");
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

  const chronoboard = useChronoboardState({
    moviesById,
    sortedMovies,
    activeMovies,
    sessions,
    onCreateSession,
    onUpdateSession,
    onCancelSession,
    onDeleteSession,
  });

  function updateMovieFormField<K extends keyof MovieCreatePayload>(field: K, value: MovieCreatePayload[K]) {
    setMovieForm((current) => ({ ...current, [field]: value }));
  }

  function resetMovieForm() {
    setMovieForm(emptyMovieForm);
    setGenresInput("");
    setEditingMovieId(null);
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

  async function handleMovieSubmit() {
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
    chronoboard.pinMovie(createdMovie.id);
  }

  async function handleDeactivateManagedMovie(movie: Movie) {
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

    if (chronoboard.pinnedMovieId === movie.id) {
      chronoboard.clearPlanningSelection();
    }
  }

  async function handleDeleteManagedMovie(movie: Movie) {
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
    if (chronoboard.pinnedMovieId === movie.id) {
      chronoboard.clearPlanningSelection();
    }
  }

  return (
    <section className="admin-stack">
      <MovieCatalogPanel
        catalogMovies={catalogMovies}
        totalMoviesCount={movies.length}
        activeMoviesCount={activeMovies.length}
        isBusy={isBusy}
        busyActionLabel={busyActionLabel}
        movieForm={movieForm}
        genresInput={genresInput}
        editingMovieId={editingMovieId}
        movieQuery={movieQuery}
        onMovieFormChange={updateMovieFormField}
        onGenresInputChange={setGenresInput}
        onMovieQueryChange={setMovieQuery}
        onSubmit={handleMovieSubmit}
        onResetForm={resetMovieForm}
        onEditMovie={handleMovieCatalogEdit}
        onQueueMovie={chronoboard.handlePlanningMovieSelect}
        onDeactivateMovie={handleDeactivateManagedMovie}
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
            editingDraft={chronoboard.editingDraft}
            selectedSession={chronoboard.selectedSession}
            draftMovie={chronoboard.draftMovie}
            editingMovie={chronoboard.editingMovie}
            movieOptionsForSessionForms={chronoboard.movieOptionsForSessionForms}
            isBusy={isBusy}
            busyActionLabel={busyActionLabel}
            onDiscardDraft={chronoboard.clearDraftPlacement}
            onUpdateDraftField={chronoboard.updateDraftField}
            onUpdateEditingDraftField={chronoboard.updateEditingDraftField}
            onResetDraftEndTime={chronoboard.resetDraftEndTime}
            onCreateDraftSession={chronoboard.handleCreateDraftSession}
            onUpdateEditedSession={chronoboard.handleUpdateEditedSession}
            onBackToSession={chronoboard.backToSession}
            onOpenEditSessionDraft={chronoboard.openEditSessionDraft}
            onCancelSelectedSession={chronoboard.handleCancelSelectedSession}
            onDeleteSelectedSession={chronoboard.handleDeleteSelectedSession}
            onJumpToToday={chronoboard.jumpToToday}
          />
        </div>
      </section>
    </section>
  );
}
