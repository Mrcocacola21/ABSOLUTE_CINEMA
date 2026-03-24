import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getScheduleRequest } from "@/api/schedule";
import { useScheduleQueryParams } from "@/hooks/useScheduleQueryParams";
import {
  filterScheduleItems,
  getAvailableMovieOptions,
  sortScheduleItems,
} from "@/shared/scheduleBrowse";
import type { ScheduleItem } from "@/types/domain";
import { ScheduleToolbar } from "@/widgets/schedule/ScheduleToolbar";

function getDayKey(value: string): string {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDayLabel(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    weekday: "short",
    day: "2-digit",
    month: "short",
  });
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "UAH",
    maximumFractionDigits: 0,
  }).format(value);
}

function getMovieMonogram(title: string): string {
  return title
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function SchedulePage() {
  const { t } = useTranslation();
  const { values, updateParam, resetParams } = useScheduleQueryParams();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    void getScheduleRequest({
      sortBy: "start_time",
      sortOrder: "asc",
      limit: "100",
      offset: "0",
    })
      .then((response) => {
        setItems(response.data);
        setErrorMessage("");
      })
      .catch(() => {
        setItems([]);
        setErrorMessage(t("backendScheduleUnavailable"));
      });
  }, [t]);

  const baseFilteredItems = useMemo(
    () => filterScheduleItems(items, values.query, values.movieId),
    [items, values.movieId, values.query],
  );

  const movieOptions = useMemo(
    () => getAvailableMovieOptions(baseFilteredItems),
    [baseFilteredItems],
  );

  const dayOptions = useMemo(() => {
    const days = new Map<string, number>();

    for (const item of sortScheduleItems(baseFilteredItems, "start_time", "asc")) {
      const dayKey = getDayKey(item.start_time);
      days.set(dayKey, (days.get(dayKey) ?? 0) + 1);
    }

    return [...days.entries()].map(([value, count]) => ({
      value,
      label: formatDayLabel(value),
      count,
    }));
  }, [baseFilteredItems]);

  const selectedDay = dayOptions.some((option) => option.value === values.day)
    ? values.day
    : dayOptions[0]?.value ?? "";

  useEffect(() => {
    if (dayOptions.length === 0) {
      if (values.day) {
        updateParam("day", "");
      }
      return;
    }

    if (!values.day || !dayOptions.some((option) => option.value === values.day)) {
      updateParam("day", dayOptions[0].value);
    }
  }, [dayOptions, updateParam, values.day]);

  const dayItems = useMemo(
    () =>
      sortScheduleItems(
        baseFilteredItems.filter((item) => getDayKey(item.start_time) === selectedDay),
        values.sortBy,
        values.sortOrder,
      ),
    [baseFilteredItems, selectedDay, values.sortBy, values.sortOrder],
  );

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
            {dayOptions.length} {t("chooseDay")}
          </span>
          <span className="badge">
            {items.length} {t("upcomingSessions")}
          </span>
        </div>
      </section>

      <section className="panel day-panel">
        <div className="toolbar-panel__header">
          <div>
            <p className="page-eyebrow">{t("chooseDay")}</p>
            <h2 className="section-title">{selectedDay ? formatDayLabel(selectedDay) : t("schedule")}</h2>
          </div>
          <p className="toolbar-panel__summary">{t("scheduleDayHint")}</p>
        </div>

        {dayOptions.length > 0 ? (
          <div className="day-pills">
            {dayOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`day-pill${option.value === selectedDay ? " is-active" : ""}`}
                onClick={() => updateParam("day", option.value)}
              >
                <strong>{option.label}</strong>
                <span>{option.count}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-state">{t("scheduleEmptyDays")}</div>
        )}
      </section>

      <ScheduleToolbar
        query={values.query}
        sortBy={values.sortBy}
        sortOrder={values.sortOrder}
        movieId={values.movieId}
        movies={movieOptions}
        resultsLabel={t("scheduleDayResultsLabel", {
          sessions: dayItems.length,
          movies: new Set(dayItems.map((item) => item.movie_id)).size,
          day: selectedDay ? formatDayLabel(selectedDay) : "-",
        })}
        onChange={updateParam}
        onReset={resetParams}
      />

      {errorMessage ? <section className="empty-state">{errorMessage}</section> : null}

      {!errorMessage && dayOptions.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("noMatchingSessions")}</h2>
          <p>{t("scheduleQueryHint")}</p>
          <button className="button--ghost" type="button" onClick={resetParams}>
            {t("resetFilters")}
          </button>
        </section>
      ) : null}

      {!errorMessage && dayOptions.length > 0 && dayItems.length === 0 ? (
        <section className="empty-state empty-state--panel">
          <h2>{t("noMatchingSessions")}</h2>
          <p>{t("scheduleQueryHint")}</p>
          <button className="button--ghost" type="button" onClick={resetParams}>
            {t("resetFilters")}
          </button>
        </section>
      ) : null}

      {!errorMessage && dayItems.length > 0 ? (
        <section className="schedule-board">
          {dayItems.map((item) => (
            <article key={item.id} className="card timeline-card">
              <div className="timeline-card__time">
                <strong>
                  {new Date(item.start_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </strong>
                <span>
                  {new Date(item.end_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>

              <div className="media-tile timeline-card__media" aria-hidden="true">
                {item.poster_url ? (
                  <img src={item.poster_url} alt="" className="media-tile__image" />
                ) : (
                  <span>{getMovieMonogram(item.movie_title)}</span>
                )}
              </div>

              <div className="timeline-card__body">
                <div className="meta-row">
                  <span className="badge">{item.status}</span>
                  {item.age_rating ? <span className="badge">{item.age_rating}</span> : null}
                  <span className="badge">
                    {item.available_seats}/{item.total_seats}
                  </span>
                </div>
                <h3>{item.movie_title}</h3>
                <p className="muted">
                  {item.genres.length > 0 ? item.genres.join(", ") : t("currentlyShowing")}
                </p>
              </div>

              <div className="timeline-card__actions">
                <span className="badge">{formatCurrency(item.price)}</span>
                <span className="badge">
                  {item.available_seats} {t("seatsLeft")}
                </span>
                <Link to={`/schedule/${item.id}`} className="button">
                  {t("viewSession")}
                </Link>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </>
  );
}
