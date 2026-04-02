import { useTranslation } from "react-i18next";

import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { BoardStats, PlannerNotice, QuickDayOption } from "@/widgets/admin/chronoboard/types";
import { formatDayLabel } from "@/widgets/admin/chronoboard/utils";

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

        <div className="day-pills">
          {quickDayOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`day-pill${option.value === selectedDay ? " is-active" : ""}`}
              onClick={() => onSelectedDayChange(option.value)}
            >
              <strong>{option.label}</strong>
              <span>
                {option.count} {t("common.labels.sessions")}
              </span>
            </button>
          ))}
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
