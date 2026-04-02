import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getGenreLabel } from "@/shared/genres";
import { getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatTime } from "@/shared/presentation";
import type { ScheduleItem } from "@/types/domain";
import { formatScheduleDayLabel, getMovieMonogram, toScheduleDayKey } from "@/shared/scheduleTimeline";

interface ScheduleCardProps {
  item: ScheduleItem;
}

export function ScheduleCard({ item }: ScheduleCardProps) {
  const { t, i18n } = useTranslation();
  const title = getLocalizedText(item.movie_title, i18n.language);
  const dayLabel = formatScheduleDayLabel(toScheduleDayKey(item.start_time));
  const timeRange = `${formatTime(item.start_time)} - ${formatTime(item.end_time)}`;

  return (
    <article className="card schedule-card">
      <div className="schedule-card__header">
        <div className="media-tile schedule-card__media" aria-hidden="true">
          {item.poster_url ? (
            <img src={item.poster_url} alt="" className="media-tile__image" />
          ) : (
            <span>{getMovieMonogram(title)}</span>
          )}
        </div>
        <div className="schedule-card__body">
          <div className="schedule-card__topline">
            <div className="schedule-card__title-row">
              <h3 className="schedule-card__title">{title}</h3>
              {item.age_rating ? <span className="badge schedule-card__age-rating">{item.age_rating}</span> : null}
            </div>

            {item.genres.length > 0 ? (
              <div className="meta-row schedule-card__taxonomy">
                {item.genres.map((genre) => (
                  <span key={`${item.id}-${genre}`} className="badge">
                    {getGenreLabel(genre, i18n.language)}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="schedule-card__facts">
            <div className="schedule-card__fact">
              <span>{t("common.labels.date")}</span>
              <strong>{dayLabel}</strong>
            </div>
            <div className="schedule-card__fact">
              <span>{t("common.labels.time")}</span>
              <strong>{timeRange}</strong>
            </div>
            <div className="schedule-card__fact">
              <span>{t("common.labels.availableSeats")}</span>
              <strong>
                {item.available_seats} / {item.total_seats}
              </strong>
            </div>
            <div className="schedule-card__fact">
              <span>{t("common.labels.price")}</span>
              <strong>{formatCurrency(item.price)}</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="schedule-card__footer">
        <div className="actions-row schedule-card__actions">
          <Link to={`/schedule/${item.id}`} className="button">
            {t("common.actions.viewSession")}
          </Link>
          <Link to={`/movies/${item.movie_id}`} className="button--ghost">
            {t("common.actions.viewMovieDetails")}
          </Link>
        </div>
      </div>
    </article>
  );
}
