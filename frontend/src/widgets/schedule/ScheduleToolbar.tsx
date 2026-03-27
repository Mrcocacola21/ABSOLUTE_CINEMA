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
            <p className="page-eyebrow">{t("browseSchedule")}</p>
            <h2 className="section-title">{t("upcomingSessions")}</h2>
            <p className="toolbar-panel__summary toolbar-panel__summary--schedule">
              {t("scheduleQueryHint")}
            </p>
          </div>

          <div className="toolbar-panel__results" aria-live="polite">
            <p className="toolbar-panel__results-value">{props.resultsLabel}</p>
          </div>
        </div>

        <div className="toolbar toolbar--schedule-list">
          <label className="field field--schedule-search">
            <span>{t("searchByTitle")}</span>
            <input
              value={props.query}
              onChange={(event) => props.onChange("query", event.target.value)}
              placeholder={t("searchPlaceholder")}
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
              {t("scheduleSearchSuggestHint", {
                defaultValue: "Start typing to see matching full movie titles.",
              })}
            </span>
          </label>

          <label className="field field--schedule-compact">
            <span>{t("chooseDay")}</span>
            <select value={props.listDay} onChange={(event) => props.onChange("listDay", event.target.value)}>
              <option value="">{t("allDays")}</option>
              {props.dayOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field field--schedule-compact">
            <span>{t("dateSortLabel", { defaultValue: "Date order" })}</span>
            <select
              value={props.dateSort}
              onChange={(event) => props.onDateSortChange(event.target.value as ScheduleDateSortMode)}
            >
              <option value="nearest">{t("nearestFirst")}</option>
              <option value="farthest">{t("farthestFirst")}</option>
            </select>
          </label>

          <label className="field field--schedule-compact">
            <span>{t("seatSortLabel", { defaultValue: "Free seats order" })}</span>
            <select
              value={props.seatSort}
              onChange={(event) => props.onSeatSortChange(event.target.value as ScheduleSeatSortMode)}
            >
              <option value="">
                {t("noSeatSorting", { defaultValue: "No seat sorting" })}
              </option>
              <option value="most_occupied">{t("mostOccupiedFirst")}</option>
              <option value="least_occupied">{t("leastOccupiedFirst")}</option>
            </select>
          </label>

          <div className="toolbar__actions toolbar__actions--schedule">
            <button className="button--ghost" type="button" onClick={props.onReset}>
              {t("resetFilters")}
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
          <p className="page-eyebrow">{t("filters")}</p>
          <h2 className="section-title">{t("browseControls")}</h2>
        </div>
        <p className="toolbar-panel__summary">{props.resultsLabel}</p>
      </div>

      <div className="toolbar">
        <label className="field field--search">
          <span>{t("searchByTitle")}</span>
          <input
            value={props.query}
            onChange={(event) => props.onChange("query", event.target.value)}
            placeholder={t("searchPlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("movie")}</span>
          <select value={props.movieId} onChange={(event) => props.onChange("movieId", event.target.value)}>
            <option value="">{t("allMovies")}</option>
            {props.movies.map((movie) => (
              <option key={movie.id} value={movie.id}>
                {movie.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("sortBy")}</span>
          <select value={props.sortBy} onChange={(event) => props.onChange("sortBy", event.target.value)}>
            <option value="start_time">{t("dateTime")}</option>
            <option value="available_seats">{t("availableSeats")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("sortOrder")}</span>
          <select value={props.sortOrder} onChange={(event) => props.onChange("sortOrder", event.target.value)}>
            <option value="asc">{t("ascending")}</option>
            <option value="desc">{t("descending")}</option>
          </select>
        </label>
        <div className="toolbar__actions">
          <button className="button--ghost" type="button" onClick={props.onReset}>
            {t("resetFilters")}
          </button>
        </div>
      </div>
    </section>
  );
}
