import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { useScheduleQueryParams } from "@/hooks/useScheduleQueryParams";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { isGenreCode } from "@/shared/genres";
import { isMovieActive } from "@/shared/movieStatus";
import { usePagination } from "@/shared/pagination";
import {
  filterBoardScheduleItems,
  filterScheduleListItems,
  getAvailableGenreOptions,
  getAvailableMovieOptions,
  getScheduleDayOptions,
  getScheduleTitleSuggestions,
  sortScheduleItems,
  sortPublicScheduleListItems,
} from "@/shared/scheduleBrowse";
import { formatScheduleDayLabel, toScheduleDayKey } from "@/shared/scheduleTimeline";
import { PaginationControls } from "@/shared/ui/PaginationControls";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";
import { ScheduleBoardControls } from "@/widgets/schedule/ScheduleBoardControls";
import { ScheduleChronoboard } from "@/widgets/schedule/ScheduleChronoboard";
import { ScheduleList } from "@/widgets/schedule/ScheduleList";
import { ScheduleToolbar } from "@/widgets/schedule/ScheduleToolbar";

const SCHEDULE_LIST_PAGE_SIZE = 6;

function buildMoviesById(movies: Movie[]): Record<string, Movie> {
  return movies.reduce<Record<string, Movie>>((accumulator, movie) => {
    accumulator[movie.id] = movie;
    return accumulator;
  }, {});
}

function normalizeDateSort(value: string): "nearest" | "farthest" {
  return value === "farthest" ? "farthest" : "nearest";
}

function normalizeSeatSort(value: string): "" | "most_occupied" | "least_occupied" {
  if (value === "most_occupied" || value === "least_occupied") {
    return value;
  }

  return "";
}

export function SchedulePage() {
  const { t, i18n } = useTranslation();
  const { values, updateParam, updateParams } = useScheduleQueryParams();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadSchedule() {
    setIsLoading(true);
    try {
      const [scheduleResponse, moviesResponse] = await Promise.all([
        getScheduleRequest({
          sortBy: "start_time",
          sortOrder: "asc",
          limit: "100",
          offset: "0",
        }),
        getMoviesRequest({ includeInactive: true }),
      ]);
      setItems(scheduleResponse.data);
      setMovies(moviesResponse.data);
      setErrorMessage("");
    } catch (error) {
      setItems([]);
      setMovies([]);
      setErrorMessage(extractApiErrorMessage(error, t("schedule.errors.unavailable")));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadSchedule();
  }, [t]);

  const moviesById = useMemo(() => buildMoviesById(movies), [movies]);
  const dateSort = normalizeDateSort(values.dateSort);
  const seatSort = normalizeSeatSort(values.seatSort);
  const allDayOptions = useMemo(() => getScheduleDayOptions(items), [items]);
  const rotationMovieCount = useMemo(
    () =>
      new Set(
        items
          .filter((item) => {
            const movie = moviesById[item.movie_id];
            return movie ? isMovieActive(movie) : true;
          })
          .map((item) => item.movie_id),
      ).size,
    [items, moviesById],
  );

  const boardMovieOptions = useMemo(() => getAvailableMovieOptions(items, i18n.language), [i18n.language, items]);
  const boardGenreOptions = useMemo(() => getAvailableGenreOptions(items, i18n.language), [i18n.language, items]);
  const selectedBoardGenre = isGenreCode(values.genre) ? values.genre : "";

  const boardBaseItems = useMemo(
    () => filterBoardScheduleItems(items, values.movieId, selectedBoardGenre),
    [items, selectedBoardGenre, values.movieId],
  );

  const boardDayOptions = useMemo(() => getScheduleDayOptions(boardBaseItems), [boardBaseItems]);

  const selectedBoardDay = boardDayOptions.some((option) => option.value === values.day)
    ? values.day
    : boardDayOptions[0]?.value ?? "";

  useEffect(() => {
    if (boardDayOptions.length === 0) {
      if (values.day) {
        updateParam("day", "");
      }
      return;
    }

    if (!values.day || !boardDayOptions.some((option) => option.value === values.day)) {
      updateParam("day", boardDayOptions[0].value);
    }
  }, [boardDayOptions, updateParam, values.day]);

  const boardItems = useMemo(
    () =>
      sortScheduleItems(
        boardBaseItems.filter((item) => toScheduleDayKey(item.start_time) === selectedBoardDay),
        "start_time",
        "asc",
        i18n.language,
      ),
    [boardBaseItems, i18n.language, selectedBoardDay],
  );

  const listBaseItems = useMemo(
    () => filterScheduleListItems(items, values.query, "", i18n.language),
    [i18n.language, items, values.query],
  );

  const listDayOptions = useMemo(() => getScheduleDayOptions(listBaseItems), [listBaseItems]);

  useEffect(() => {
    if (values.listDay && !listDayOptions.some((option) => option.value === values.listDay)) {
      updateParam("listDay", "");
    }
  }, [listDayOptions, updateParam, values.listDay]);

  const listFilteredItems = useMemo(
    () => filterScheduleListItems(items, values.query, values.listDay, i18n.language),
    [i18n.language, items, values.listDay, values.query],
  );

  const listSuggestionPool = useMemo(
    () => filterScheduleListItems(items, "", values.listDay, i18n.language),
    [i18n.language, items, values.listDay],
  );

  const listQuerySuggestions = useMemo(
    () => getScheduleTitleSuggestions(listSuggestionPool, values.query, i18n.language),
    [i18n.language, listSuggestionPool, values.query],
  );

  const listItems = useMemo(
    () => sortPublicScheduleListItems(listFilteredItems, dateSort, seatSort, i18n.language),
    [dateSort, i18n.language, listFilteredItems, seatSort],
  );

  const scheduleListPagination = usePagination(listItems, {
    pageSize: SCHEDULE_LIST_PAGE_SIZE,
    resetKey: JSON.stringify({
      dateSort,
      listDay: values.listDay,
      query: values.query,
      seatSort,
    }),
  });

  const boardResultsLabel = t("schedule.board.resultsLabel", {
    sessions: boardItems.length,
    movies: new Set(boardItems.map((item) => item.movie_id)).size,
    day: selectedBoardDay ? formatScheduleDayLabel(selectedBoardDay) : "-",
  });

  const listResultsLabel = t("schedule.list.resultsLabel", {
    sessions: listItems.length,
    movies: new Set(listItems.map((item) => item.movie_id)).size,
  });

  function resetBoardFilters() {
    updateParams({
      day: "",
      genre: "",
      movieId: "",
      sessionId: "",
    });
  }

  function handleBoardDayChange(day: string) {
    updateParams({
      day,
      sessionId: "",
    });
  }

  function handleBoardFilterChange(key: "movieId" | "genre", value: string) {
    updateParams({
      [key]: value,
      sessionId: "",
    });
  }

  function resetListFilters() {
    updateParams({
      listDay: "",
      query: "",
      dateSort: "nearest",
      seatSort: "",
    });
  }

  function handleDateSortChange(nextDateSort: "nearest" | "farthest") {
    updateParam("dateSort", nextDateSort);
  }

  function handleSeatSortChange(nextSeatSort: "" | "most_occupied" | "least_occupied") {
    updateParam("seatSort", nextSeatSort);
  }

  return (
    <>
      <section className="page-header">
        <div>
          <p className="page-eyebrow">{t("schedule.page.eyebrow")}</p>
          <h1 className="page-title">{t("schedule.page.title")}</h1>
          <p className="page-subtitle">{t("schedule.page.intro")}</p>
        </div>
        <div className="stats-row">
          <span className="badge">
            {allDayOptions.length} {t("schedule.board.dayLabel")}
          </span>
          <span className="badge">
            {rotationMovieCount} {t("common.labels.activeNow")}
          </span>
          <span className="badge">
            {items.length} {t("common.labels.upcomingSessions")}
          </span>
        </div>
      </section>

      {isLoading ? (
        <StatePanel
          tone="loading"
          title={t("schedule.loading.title")}
          message={t("schedule.loading.message")}
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title={t("schedule.errors.title")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadSchedule()}>
              {t("common.actions.retry")}
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage && items.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("schedule.list.noSessionsYetTitle")}</h2>
          <p>{t("schedule.list.queryHint")}</p>
        </section>
      ) : null}

      {!isLoading && !errorMessage && items.length > 0 ? (
        <section className="schedule-section-stack">
          <ScheduleBoardControls
            selectedDay={selectedBoardDay}
            dayOptions={boardDayOptions}
            movieId={values.movieId}
            genre={selectedBoardGenre}
            movies={boardMovieOptions}
            genres={boardGenreOptions}
            resultsLabel={boardResultsLabel}
            onDayChange={handleBoardDayChange}
            onFilterChange={handleBoardFilterChange}
            onReset={resetBoardFilters}
          />

          {boardDayOptions.length === 0 || !selectedBoardDay || boardItems.length === 0 ? (
            <section className="empty-state empty-state--panel">
              <h2>{t("schedule.list.noMatchingTitle")}</h2>
              <p>{t("schedule.board.hint")}</p>
              <button className="button--ghost" type="button" onClick={resetBoardFilters}>
                {t("common.actions.resetFilters")}
              </button>
            </section>
          ) : (
            <ScheduleChronoboard
              items={boardItems}
              selectedDay={selectedBoardDay}
              highlightedSessionId={values.sessionId}
            />
          )}
        </section>
      ) : null}

      {!isLoading && !errorMessage && items.length > 0 ? (
        <section className="schedule-section-stack">
          <ScheduleToolbar
            query={values.query}
            dateSort={dateSort}
            seatSort={seatSort}
            listDay={values.listDay}
            dayOptions={listDayOptions}
            querySuggestions={listQuerySuggestions}
            resultsLabel={listResultsLabel}
            onChange={updateParam}
            onDateSortChange={handleDateSortChange}
            onSeatSortChange={handleSeatSortChange}
            onReset={resetListFilters}
          />

          <section className="panel public-schedule-list-panel">
            <div className="toolbar-panel__header">
              <div>
                <p className="page-eyebrow">{t("common.actions.browseSchedule")}</p>
                <h2 className="section-title">{t("common.labels.upcomingSessions")}</h2>
                <p className="toolbar-panel__summary">{t("schedule.list.queryHint")}</p>
              </div>
              <div className="stats-row">
                <span className="badge">
                  {listItems.length} {t("common.labels.upcomingSessions")}
                </span>
                <span className="badge">
                  {new Set(listItems.map((item) => item.movie_id)).size} {t("common.labels.movies")}
                </span>
              </div>
            </div>

            <ScheduleList items={scheduleListPagination.pageItems} />

            <PaginationControls
              page={scheduleListPagination.page}
              totalPages={scheduleListPagination.totalPages}
              onPageChange={scheduleListPagination.setPage}
            />
          </section>
        </section>
      ) : null}
    </>
  );
}
