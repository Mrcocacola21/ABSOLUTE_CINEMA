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
  return (
    <>
      <div className="admin-board-context">
        <div className="admin-board-context__hero">
          <div className="admin-board-context__copy">
            <p className="admin-board-context__eyebrow">Board For</p>
            <h2 className="admin-board-context__title">{formatDayLabel(selectedDay)}</h2>
            <p className="admin-board-context__subtitle">
              One hall, one timeline. Stage drafts on the board first, then confirm them from the inspector.
            </p>
          </div>
          <div className="admin-board-context__controls">
            <label className="field">
              <span>Board date</span>
              <input type="date" value={selectedDay} onChange={(event) => onSelectedDayChange(event.target.value)} />
            </label>
            <div className="actions-row">
              <button className="button--ghost" type="button" onClick={onJumpToToday}>
                Today
              </button>
              {hasDraft ? (
                <button className="button--ghost" type="button" onClick={onDiscardDraft}>
                  Discard draft
                </button>
              ) : null}
            </div>
          </div>
        </div>

        <div className="stats-row">
          <span className="badge">{boardStats.sessions} sessions</span>
          <span className="badge">{boardStats.soldTickets} tickets sold</span>
          <span className="badge">{boardStats.availableSeats} seats open</span>
          {hasDraft ? <span className="badge">1 draft pending</span> : null}
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
              <span>{option.count} sessions</span>
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
              Dismiss
            </button>
          }
        />
      ) : null}
    </>
  );
}
