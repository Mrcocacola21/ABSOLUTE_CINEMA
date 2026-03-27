import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { useScheduleQueryParams } from "@/hooks/useScheduleQueryParams";
import { extractApiErrorMessage } from "@/shared/apiErrors";
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
import { StatePanel } from "@/shared/ui/StatePanel";
import type { Movie, ScheduleItem } from "@/types/domain";
import { ScheduleBoardControls } from "@/widgets/schedule/ScheduleBoardControls";
import { ScheduleChronoboard } from "@/widgets/schedule/ScheduleChronoboard";
import { ScheduleList } from "@/widgets/schedule/ScheduleList";
import { ScheduleToolbar } from "@/widgets/schedule/ScheduleToolbar";

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
  const { t } = useTranslation();
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
      setErrorMessage(extractApiErrorMessage(error, t("backendScheduleUnavailable")));
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
            return movie ? movie.is_active : true;
          })
          .map((item) => item.movie_id),
      ).size,
    [items, moviesById],
  );

  const boardMovieOptions = useMemo(() => getAvailableMovieOptions(items), [items]);
  const boardGenreOptions = useMemo(() => getAvailableGenreOptions(items), [items]);

  const boardBaseItems = useMemo(
    () => filterBoardScheduleItems(items, values.movieId, values.genre),
    [items, values.genre, values.movieId],
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
      ),
    [boardBaseItems, selectedBoardDay],
  );

  const listBaseItems = useMemo(
    () => filterScheduleListItems(items, values.query, ""),
    [items, values.query],
  );

  const listDayOptions = useMemo(() => getScheduleDayOptions(listBaseItems), [listBaseItems]);

  useEffect(() => {
    if (values.listDay && !listDayOptions.some((option) => option.value === values.listDay)) {
      updateParam("listDay", "");
    }
  }, [listDayOptions, updateParam, values.listDay]);

  const listFilteredItems = useMemo(
    () => filterScheduleListItems(items, values.query, values.listDay),
    [items, values.listDay, values.query],
  );

  const listSuggestionPool = useMemo(
    () => filterScheduleListItems(items, "", values.listDay),
    [items, values.listDay],
  );

  const listQuerySuggestions = useMemo(
    () => getScheduleTitleSuggestions(listSuggestionPool, values.query),
    [listSuggestionPool, values.query],
  );

  const listItems = useMemo(
    () => sortPublicScheduleListItems(listFilteredItems, dateSort, seatSort),
    [dateSort, listFilteredItems, seatSort],
  );

  const boardResultsLabel = t("scheduleDayResultsLabel", {
    sessions: boardItems.length,
    movies: new Set(boardItems.map((item) => item.movie_id)).size,
    day: selectedBoardDay ? formatScheduleDayLabel(selectedBoardDay) : "-",
  });

  const listResultsLabel = t("scheduleResultsLabel", {
    sessions: listItems.length,
    movies: new Set(listItems.map((item) => item.movie_id)).size,
  });

  function resetBoardFilters() {
    updateParams({
      day: "",
      genre: "",
      movieId: "",
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
          <p className="page-eyebrow">{t("scheduleEyebrow")}</p>
          <h1 className="page-title">{t("schedule")}</h1>
          <p className="page-subtitle">{t("scheduleIntro")}</p>
        </div>
        <div className="stats-row">
          <span className="badge">
            {allDayOptions.length} {t("chooseDay")}
          </span>
          <span className="badge">
            {rotationMovieCount} {t("currentlyShowing")}
          </span>
          <span className="badge">
            {items.length} {t("upcomingSessions")}
          </span>
        </div>
      </section>

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading the schedule"
          message="Fetching upcoming sessions, available days, and public movie filters."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title="Unable to load the schedule"
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadSchedule()}>
              Try again
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage && items.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("noSessionsYet")}</h2>
          <p>{t("scheduleQueryHint")}</p>
        </section>
      ) : null}

      {!isLoading && !errorMessage && items.length > 0 ? (
        <section className="schedule-section-stack">
          <ScheduleBoardControls
            selectedDay={selectedBoardDay}
            dayOptions={boardDayOptions}
            movieId={values.movieId}
            genre={values.genre}
            movies={boardMovieOptions}
            genres={boardGenreOptions}
            resultsLabel={boardResultsLabel}
            onDayChange={(day) => updateParam("day", day)}
            onFilterChange={updateParam}
            onReset={resetBoardFilters}
          />

          {boardDayOptions.length === 0 || !selectedBoardDay || boardItems.length === 0 ? (
            <section className="empty-state empty-state--panel">
              <h2>{t("noMatchingSessions")}</h2>
              <p>{t("scheduleDayHint")}</p>
              <button className="button--ghost" type="button" onClick={resetBoardFilters}>
                {t("resetFilters")}
              </button>
            </section>
          ) : (
            <ScheduleChronoboard items={boardItems} selectedDay={selectedBoardDay} />
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
                <p className="page-eyebrow">{t("browseSchedule")}</p>
                <h2 className="section-title">{t("upcomingSessions")}</h2>
                <p className="toolbar-panel__summary">{t("scheduleQueryHint")}</p>
              </div>
              <div className="stats-row">
                <span className="badge">
                  {listItems.length} {t("upcomingSessions")}
                </span>
                <span className="badge">
                  {new Set(listItems.map((item) => item.movie_id)).size} {t("movies")}
                </span>
              </div>
            </div>

            <ScheduleList items={listItems} />
          </section>
        </section>
      ) : null}
    </>
  );
}
