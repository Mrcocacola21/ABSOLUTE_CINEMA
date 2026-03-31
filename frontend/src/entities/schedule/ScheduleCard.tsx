import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { formatCurrency, formatTime } from "@/shared/presentation";
import type { ScheduleItem } from "@/types/domain";
import { formatScheduleDayLabel, getMovieMonogram, toScheduleDayKey } from "@/shared/scheduleTimeline";

interface ScheduleCardProps {
  item: ScheduleItem;
}

export function ScheduleCard({ item }: ScheduleCardProps) {
  const { t, i18n } = useTranslation();
  const dayLabel = formatScheduleDayLabel(toScheduleDayKey(item.start_time));
  const timeRange = `${formatTime(item.start_time)} - ${formatTime(item.end_time)}`;
  const dateLabel = i18n.language.startsWith("uk") ? "\u0414\u0430\u0442\u0430" : "Date";
  const timeLabel = i18n.language.startsWith("uk") ? "\u0427\u0430\u0441" : "Time";

  return (
    <article className="card schedule-card">
      <div className="schedule-card__header">
        <div className="media-tile schedule-card__media" aria-hidden="true">
          {item.poster_url ? (
            <img src={item.poster_url} alt="" className="media-tile__image" />
          ) : (
            <span>{getMovieMonogram(item.movie_title)}</span>
          )}
        </div>
        <div className="schedule-card__body">
          <div className="schedule-card__topline">
            <div className="schedule-card__title-row">
              <h3 className="schedule-card__title">{item.movie_title}</h3>
              {item.age_rating ? <span className="badge schedule-card__age-rating">{item.age_rating}</span> : null}
            </div>

            {item.genres.length > 0 ? (
              <div className="meta-row schedule-card__taxonomy">
                {item.genres.map((genre) => (
                  <span key={`${item.id}-${genre}`} className="badge">
                    {genre}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="schedule-card__facts">
            <div className="schedule-card__fact">
              <span>{dateLabel}</span>
              <strong>{dayLabel}</strong>
            </div>
            <div className="schedule-card__fact">
              <span>{timeLabel}</span>
              <strong>{timeRange}</strong>
            </div>
            <div className="schedule-card__fact">
              <span>{t("availableSeats")}</span>
              <strong>
                {item.available_seats} / {item.total_seats}
              </strong>
            </div>
            <div className="schedule-card__fact">
              <span>{t("price")}</span>
              <strong>{formatCurrency(item.price)}</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="schedule-card__footer">
        <div className="actions-row schedule-card__actions">
          <Link to={`/schedule/${item.id}`} className="button">
            {t("viewSession")}
          </Link>
          <Link to={`/movies/${item.movie_id}`} className="button--ghost">
            {t("movieDetails")}
          </Link>
        </div>
      </div>
    </article>
  );
}
