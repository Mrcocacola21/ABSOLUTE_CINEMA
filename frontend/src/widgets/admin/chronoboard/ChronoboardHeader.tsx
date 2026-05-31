import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";

import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { BoardStats, PlannerNotice, QuickDayOption } from "@/widgets/admin/chronoboard/types";
import { formatDayLabel, formatDayPillLabel } from "@/widgets/admin/chronoboard/utils";

interface ChronoboardHeaderProps {
  selectedDay: string;
  quickDayOptions: QuickDayOption[];
  boardStats: BoardStats;
  hasDraft: boolean;
  plannerNotice: PlannerNotice | null;
  onSelectedDayChange: (value: string) => void;
  onJumpToToday: () => void;
  onDiscardDraft: () => void;
  onDismissNotice: () => void;
}

export function ChronoboardHeader({
  selectedDay,
  quickDayOptions,
  boardStats,
  hasDraft,
  plannerNotice,
  onSelectedDayChange,
  onJumpToToday,
  onDiscardDraft,
  onDismissNotice,
}: ChronoboardHeaderProps) {
  const { t } = useTranslation();
  const dayPillsRef = useRef<HTMLDivElement | null>(null);
  const selectedDayIndex = useMemo(
    () => quickDayOptions.findIndex((option) => option.value === selectedDay),
    [quickDayOptions, selectedDay],
  );
  const previousDay = selectedDayIndex > 0 ? quickDayOptions[selectedDayIndex - 1] : null;
  const nextDay =
    selectedDayIndex >= 0 && selectedDayIndex < quickDayOptions.length - 1
      ? quickDayOptions[selectedDayIndex + 1]
      : null;

  useEffect(() => {
    const activeDay = dayPillsRef.current?.querySelector<HTMLButtonElement>(".day-pill.is-active");
    activeDay?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [quickDayOptions, selectedDay]);

  return (
    <>
      <div className="admin-board-context">
        <div className="admin-board-context__hero">
          <div className="admin-board-context__copy">
            <p className="admin-board-context__eyebrow">{t("chronoboard.header.eyebrow")}</p>
            <h2 className="admin-board-context__title">{formatDayLabel(selectedDay)}</h2>
            <p className="admin-board-context__subtitle">{t("chronoboard.header.subtitle")}</p>
          </div>
          <div className="admin-board-context__controls">
            <label className="field">
              <span>{t("common.labels.boardDate")}</span>
              <input type="date" value={selectedDay} onChange={(event) => onSelectedDayChange(event.target.value)} />
            </label>
            <div className="actions-row">
              <button className="button--ghost" type="button" onClick={onJumpToToday}>
                {t("common.actions.today")}
              </button>
              {hasDraft ? (
                <button className="button--ghost" type="button" onClick={onDiscardDraft}>
                  {t("common.actions.discardDraft")}
                </button>
              ) : null}
            </div>
          </div>
        </div>

        <div className="stats-row">
          <span className="badge">{boardStats.sessions} {t("common.labels.sessions")}</span>
          <span className="badge">{boardStats.soldTickets} {t("common.labels.ticketsSold")}</span>
          <span className="badge">{boardStats.availableSeats} {t("common.labels.availableSeats")}</span>
          {hasDraft ? <span className="badge">{t("chronoboard.header.draftPending")}</span> : null}
        </div>

        <div className="day-pills-shell">
          <button
            className="day-pills-nav"
            type="button"
            aria-label={t("chronoboard.header.previousDay")}
            onClick={() => previousDay && onSelectedDayChange(previousDay.value)}
            disabled={!previousDay}
          >
            <span aria-hidden="true">&lt;</span>
          </button>

          <div ref={dayPillsRef} className="day-pills" role="listbox" aria-label={t("chronoboard.header.daySelector")}>
            {quickDayOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={option.value === selectedDay}
                className={`day-pill${option.value === selectedDay ? " is-active" : ""}`}
                onClick={() => onSelectedDayChange(option.value)}
              >
                <strong>{formatDayPillLabel(option.value)}</strong>
                <span>
                  {option.count} {t("common.labels.sessions")}
                </span>
              </button>
            ))}
          </div>

          <button
            className="day-pills-nav"
            type="button"
            aria-label={t("chronoboard.header.nextDay")}
            onClick={() => nextDay && onSelectedDayChange(nextDay.value)}
            disabled={!nextDay}
          >
            <span aria-hidden="true">&gt;</span>
          </button>

          <select
            className="day-pills__select"
            value={selectedDay}
            aria-label={t("chronoboard.header.jumpToDay")}
            onChange={(event) => onSelectedDayChange(event.target.value)}
          >
            {quickDayOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {formatDayLabel(option.value)} ({option.count} {t("common.labels.sessions")})
              </option>
            ))}
          </select>
        </div>
      </div>

      {plannerNotice ? (
        <StatusBanner
          tone={plannerNotice.tone}
          title={plannerNotice.title}
          message={plannerNotice.message}
          action={
            <button className="button--ghost" type="button" onClick={onDismissNotice}>
              {t("common.actions.dismiss")}
            </button>
          }
        />
      ) : null}
    </>
  );
}
