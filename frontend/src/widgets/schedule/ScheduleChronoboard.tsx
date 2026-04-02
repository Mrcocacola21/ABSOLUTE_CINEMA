import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatTime } from "@/shared/presentation";
import {
  PUBLIC_SCHEDULE_BOARD_WIDTH,
  PUBLIC_SCHEDULE_END_HOUR,
  PUBLIC_SCHEDULE_PIXELS_PER_MINUTE,
  PUBLIC_SCHEDULE_START_HOUR,
  formatScheduleDayLabel,
  getNowMarkerOffsetForScheduleDay,
  getPublicScheduleCardStyle,
} from "@/shared/scheduleTimeline";
import type { ScheduleItem } from "@/types/domain";

interface ScheduleChronoboardProps {
  items: ScheduleItem[];
  selectedDay: string;
  highlightedSessionId?: string;
}

interface MenuPosition {
  left: number;
  top: number;
  placement: "top" | "bottom";
}

const VIEWPORT_MARGIN = 12;
const MENU_GAP = 10;

const boardHourMarkers = Array.from(
  { length: PUBLIC_SCHEDULE_END_HOUR - PUBLIC_SCHEDULE_START_HOUR + 1 },
  (_, index) => {
    const hour = PUBLIC_SCHEDULE_START_HOUR + index;
    return {
      label: `${String(hour).padStart(2, "0")}:00`,
      left: `${(hour - PUBLIC_SCHEDULE_START_HOUR) * 60 * PUBLIC_SCHEDULE_PIXELS_PER_MINUTE}px`,
    };
  },
);

const boardHourLines = Array.from(
  { length: PUBLIC_SCHEDULE_END_HOUR - PUBLIC_SCHEDULE_START_HOUR + 1 },
  (_, index) => ({
    key: index,
    left: `${index * 60 * PUBLIC_SCHEDULE_PIXELS_PER_MINUTE}px`,
  }),
);

function getPosterBackgroundValue(posterUrl?: string | null): string {
  return posterUrl ? `url("${posterUrl}")` : "none";
}

export function ScheduleChronoboard({ items, selectedDay, highlightedSessionId = "" }: ScheduleChronoboardProps) {
  const { t, i18n } = useTranslation();
  const frameRef = useRef<HTMLDivElement | null>(null);
  const anchorRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);

  const activeMenuItem = useMemo(
    () => items.find((item) => item.id === activeSessionId) ?? null,
    [activeSessionId, items],
  );

  const uniqueMoviesCount = useMemo(
    () => new Set(items.map((item) => item.movie_id)).size,
    [items],
  );

  const firstSession = items[0] ?? null;
  const lastSession = items[items.length - 1] ?? null;
  const nowMarkerOffset = getNowMarkerOffsetForScheduleDay(selectedDay);

  function closeMenu() {
    setActiveSessionId(null);
    setMenuPosition(null);
    anchorRef.current = null;
  }

  function updateMenuPosition() {
    if (!anchorRef.current || !menuRef.current) {
      return;
    }

    const anchorRect = anchorRef.current.getBoundingClientRect();
    const menuRect = menuRef.current.getBoundingClientRect();
    const fitsBelow = anchorRect.bottom + MENU_GAP + menuRect.height <= window.innerHeight - VIEWPORT_MARGIN;
    const fitsAbove = anchorRect.top - MENU_GAP - menuRect.height >= VIEWPORT_MARGIN;

    let top = fitsBelow
      ? anchorRect.bottom + MENU_GAP
      : fitsAbove
        ? anchorRect.top - menuRect.height - MENU_GAP
        : Math.max(
            VIEWPORT_MARGIN,
            Math.min(anchorRect.bottom + MENU_GAP, window.innerHeight - menuRect.height - VIEWPORT_MARGIN),
          );

    let left = anchorRect.left + anchorRect.width / 2 - menuRect.width / 2;
    left = Math.max(VIEWPORT_MARGIN, Math.min(left, window.innerWidth - menuRect.width - VIEWPORT_MARGIN));
    top = Math.max(VIEWPORT_MARGIN, Math.min(top, window.innerHeight - menuRect.height - VIEWPORT_MARGIN));

    setMenuPosition({
      left,
      top,
      placement: fitsBelow || !fitsAbove ? "bottom" : "top",
    });
  }

  useEffect(() => {
    if (activeSessionId && !items.some((item) => item.id === activeSessionId)) {
      closeMenu();
    }
  }, [activeSessionId, items]);

  useEffect(() => {
    if (!highlightedSessionId || !items.some((item) => item.id === highlightedSessionId)) {
      return;
    }

    const target = frameRef.current?.querySelector<HTMLElement>(`[data-session-id="${highlightedSessionId}"]`);
    if (!target) {
      return;
    }

    window.requestAnimationFrame(() => {
      target.scrollIntoView({
        block: "nearest",
        inline: "center",
        behavior: "smooth",
      });
    });
  }, [highlightedSessionId, items, selectedDay]);

  useLayoutEffect(() => {
    if (!activeMenuItem) {
      return;
    }

    updateMenuPosition();
  }, [activeMenuItem]);

  useEffect(() => {
    if (!activeSessionId) {
      return;
    }

    const frameElement = frameRef.current;

    function handleReposition() {
      if (!anchorRef.current || !anchorRef.current.isConnected) {
        closeMenu();
        return;
      }

      updateMenuPosition();
    }

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;

      if (!(target instanceof Element)) {
        closeMenu();
        return;
      }

      if (menuRef.current?.contains(target)) {
        return;
      }

      if (target.closest(".public-chrono-session")) {
        return;
      }

      closeMenu();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeMenu();
      }
    }

    window.addEventListener("resize", handleReposition);
    window.addEventListener("scroll", handleReposition, true);
    frameElement?.addEventListener("scroll", handleReposition, { passive: true });
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("resize", handleReposition);
      window.removeEventListener("scroll", handleReposition, true);
      frameElement?.removeEventListener("scroll", handleReposition);
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeSessionId]);

  function handleSessionClick(itemId: string, event: ReactMouseEvent<HTMLButtonElement>) {
    if (activeSessionId === itemId) {
      closeMenu();
      return;
    }

    anchorRef.current = event.currentTarget;
    setMenuPosition(null);
    setActiveSessionId(itemId);
  }

  const menu =
    activeMenuItem
      ? createPortal(
          <div
            ref={menuRef}
            className="public-chrono-menu"
            data-placement={menuPosition?.placement ?? "bottom"}
            style={{
              left: `${menuPosition?.left ?? 0}px`,
              top: `${menuPosition?.top ?? 0}px`,
              opacity: menuPosition ? 1 : 0,
              pointerEvents: menuPosition ? "auto" : "none",
            }}
          >
            <div className="public-chrono-menu__header">
              <div>
                <strong>{getLocalizedText(activeMenuItem.movie_title, i18n.language)}</strong>
                <p>
                  {formatTime(activeMenuItem.start_time)} - {formatTime(activeMenuItem.end_time)}
                </p>
                <p className="public-chrono-menu__summary">
                  {formatCurrency(activeMenuItem.price)} | {activeMenuItem.available_seats}/{activeMenuItem.total_seats}
                </p>
              </div>
              <button
                className="public-chrono-menu__dismiss"
                type="button"
                onClick={closeMenu}
                aria-label={t("schedule.quickActions.closeQuickActions")}
              >
                x
              </button>
            </div>

            <div className="public-chrono-menu__actions">
              <Link to={`/schedule/${activeMenuItem.id}`} className="button">
                {t("common.actions.viewSession")}
              </Link>
              <Link to={`/movies/${activeMenuItem.movie_id}`} className="button--ghost">
                {t("common.actions.viewMovieDetails")}
              </Link>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <section className="panel public-chrono">
        <div className="public-chrono__header">
          <div>
            <p className="page-eyebrow">{t("schedule.board.title")}</p>
            <h2 className="section-title">{formatScheduleDayLabel(selectedDay)}</h2>
            <p className="muted">{t("schedule.board.hint")}</p>
          </div>

          <div className="stats-row public-chrono__stats">
            <span className="badge">
              {items.length} {t("common.labels.upcomingSessions")}
            </span>
            <span className="badge">
              {uniqueMoviesCount} {t("common.labels.movies")}
            </span>
            {firstSession && lastSession ? (
              <span className="badge">
                {formatTime(firstSession.start_time)} - {formatTime(lastSession.end_time)}
              </span>
            ) : null}
          </div>
        </div>

        <div ref={frameRef} className="public-chrono__frame">
          <div className="public-chrono__board" style={{ width: `${PUBLIC_SCHEDULE_BOARD_WIDTH}px` }}>
            <div className="public-chrono__scale">
              {boardHourMarkers.map((marker) => (
                <div key={marker.label} className="public-chrono__hour-label" style={{ left: marker.left }}>
                  {marker.label}
                </div>
              ))}
            </div>

            <div className="public-chrono__lane">
              {boardHourLines.map((line) => (
                <div key={line.key} className="public-chrono__hour-line" style={{ left: line.left }} />
              ))}

              {nowMarkerOffset ? <div className="public-chrono__now" style={{ left: nowMarkerOffset }} /> : null}

              {items.map((item) => {
                const soldSeats = item.total_seats - item.available_seats;

                return (
                  <button
                    key={item.id}
                    type="button"
                    data-session-id={item.id}
                    className={`public-chrono-session public-chrono-session--${item.status}${activeSessionId === item.id ? " is-active" : ""}${highlightedSessionId === item.id ? " is-targeted" : ""}`}
                    style={{
                      ...getPublicScheduleCardStyle(item.start_time, item.end_time),
                      ["--public-chrono-poster" as string]: getPosterBackgroundValue(item.poster_url),
                    }}
                    onClick={(event) => handleSessionClick(item.id, event)}
                    aria-pressed={activeSessionId === item.id}
                  >
                    <div className="public-chrono-session__header">
                      <strong title={getLocalizedText(item.movie_title, i18n.language)}>
                        {getLocalizedText(item.movie_title, i18n.language)}
                      </strong>
                    </div>
                    <p className="public-chrono-session__time">
                      {formatTime(item.start_time)} - {formatTime(item.end_time)}
                    </p>
                    <div className="public-chrono-session__footer">
                      <span className="public-chrono-session__stat">
                        {item.available_seats} {t("common.stats.seatsLeft")}
                      </span>
                      <span className="public-chrono-session__stat public-chrono-session__stat--muted">
                        {soldSeats} {t("common.stats.sold")}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {menu}
    </>
  );
}
