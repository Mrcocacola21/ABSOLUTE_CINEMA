import { useId } from "react";
import { useTranslation } from "react-i18next";

import type {
  MovieOption,
  ScheduleDateSortMode,
  ScheduleDayOption,
  ScheduleSeatSortMode,
} from "@/shared/scheduleBrowse";

interface BaseToolbarProps {
  query: string;
  resultsLabel: string;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
}

interface HomeScheduleToolbarProps extends BaseToolbarProps {
  sortBy: string;
  sortOrder: string;
  movieId: string;
  movies: MovieOption[];
  dateSort?: never;
  seatSort?: never;
  dayOptions?: never;
  listDay?: never;
  querySuggestions?: never;
  onDateSortChange?: never;
  onSeatSortChange?: never;
}

interface PublicScheduleToolbarProps extends BaseToolbarProps {
  dateSort: ScheduleDateSortMode;
  seatSort: ScheduleSeatSortMode;
  listDay: string;
  dayOptions: ScheduleDayOption[];
  querySuggestions: string[];
  onDateSortChange: (sortMode: ScheduleDateSortMode) => void;
  onSeatSortChange: (sortMode: ScheduleSeatSortMode) => void;
  sortBy?: never;
  sortOrder?: never;
  movieId?: never;
  movies?: never;
}

type ScheduleToolbarProps = HomeScheduleToolbarProps | PublicScheduleToolbarProps;

function isPublicScheduleToolbar(
  props: ScheduleToolbarProps,
): props is PublicScheduleToolbarProps {
  return "dayOptions" in props;
}

export function ScheduleToolbar(props: ScheduleToolbarProps) {
  const { t } = useTranslation();
  const suggestionListId = useId();

  if (isPublicScheduleToolbar(props)) {
    return (
      <section className="panel toolbar-panel toolbar-panel--schedule">
        <div className="toolbar-panel__header toolbar-panel__header--schedule">
          <div className="toolbar-panel__intro">
            <p className="page-eyebrow">{t("common.actions.browseSchedule")}</p>
            <h2 className="section-title">{t("common.labels.upcomingSessions")}</h2>
            <p className="toolbar-panel__summary toolbar-panel__summary--schedule">
              {t("schedule.list.queryHint")}
            </p>
          </div>

          <div className="toolbar-panel__results" aria-live="polite">
            <p className="toolbar-panel__results-value">{props.resultsLabel}</p>
          </div>
        </div>

        <div className="toolbar toolbar--schedule-list">
          <label className="field field--schedule-search">
            <span>{t("movies.filters.searchByTitle")}</span>
            <input
              value={props.query}
              onChange={(event) => props.onChange("query", event.target.value)}
              placeholder={t("movies.filters.searchPlaceholder")}
              list={props.querySuggestions.length > 0 ? suggestionListId : undefined}
              autoComplete="off"
            />
            {props.querySuggestions.length > 0 ? (
              <datalist id={suggestionListId}>
                {props.querySuggestions.map((title) => (
                  <option key={title} value={title} />
                ))}
              </datalist>
            ) : null}
            <span className="field__hint">
              {t("schedule.list.searchSuggestHint")}
            </span>
          </label>

          <label className="field field--schedule-compact">
            <span>{t("schedule.board.dayLabel")}</span>
            <select value={props.listDay} onChange={(event) => props.onChange("listDay", event.target.value)}>
              <option value="">{t("common.labels.allDays")}</option>
              {props.dayOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field field--schedule-compact">
            <span>{t("schedule.list.sort.dateOrder")}</span>
            <select
              value={props.dateSort}
              onChange={(event) => props.onDateSortChange(event.target.value as ScheduleDateSortMode)}
            >
              <option value="nearest">{t("schedule.list.sort.nearestFirst")}</option>
              <option value="farthest">{t("schedule.list.sort.farthestFirst")}</option>
            </select>
          </label>

          <label className="field field--schedule-compact">
            <span>{t("schedule.list.sort.freeSeatsOrder")}</span>
            <select
              value={props.seatSort}
              onChange={(event) => props.onSeatSortChange(event.target.value as ScheduleSeatSortMode)}
            >
              <option value="">{t("schedule.list.sort.noSeatSorting")}</option>
              <option value="most_occupied">{t("schedule.list.sort.mostOccupiedFirst")}</option>
              <option value="least_occupied">{t("schedule.list.sort.leastOccupiedFirst")}</option>
            </select>
          </label>

          <div className="toolbar__actions toolbar__actions--schedule">
            <button className="button--ghost" type="button" onClick={props.onReset}>
              {t("common.actions.resetFilters")}
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel toolbar-panel">
      <div className="toolbar-panel__header">
        <div>
          <p className="page-eyebrow">{t("common.labels.filters")}</p>
          <h2 className="section-title">{t("common.labels.browseControls")}</h2>
        </div>
        <p className="toolbar-panel__summary">{props.resultsLabel}</p>
      </div>

      <div className="toolbar">
        <label className="field field--search">
          <span>{t("movies.filters.searchByTitle")}</span>
          <input
            value={props.query}
            onChange={(event) => props.onChange("query", event.target.value)}
            placeholder={t("movies.filters.searchPlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("common.labels.movie")}</span>
          <select value={props.movieId} onChange={(event) => props.onChange("movieId", event.target.value)}>
            <option value="">{t("common.labels.allMovies")}</option>
            {props.movies.map((movie) => (
              <option key={movie.id} value={movie.id}>
                {movie.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("common.labels.sortBy")}</span>
          <select value={props.sortBy} onChange={(event) => props.onChange("sortBy", event.target.value)}>
            <option value="start_time">{t("common.labels.dateTime")}</option>
            <option value="available_seats">{t("common.labels.availableSeats")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("schedule.list.sort.dateOrder")}</span>
          <select value={props.sortOrder} onChange={(event) => props.onChange("sortOrder", event.target.value)}>
            <option value="asc">{t("common.sort.ascending")}</option>
            <option value="desc">{t("common.sort.descending")}</option>
          </select>
        </label>
        <div className="toolbar__actions">
          <button className="button--ghost" type="button" onClick={props.onReset}>
            {t("common.actions.resetFilters")}
          </button>
        </div>
      </div>
    </section>
  );
}
