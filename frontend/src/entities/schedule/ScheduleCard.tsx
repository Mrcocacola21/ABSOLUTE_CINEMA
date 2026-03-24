import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { ScheduleItem } from "@/types/domain";

interface ScheduleCardProps {
  item: ScheduleItem;
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

export function ScheduleCard({ item }: ScheduleCardProps) {
  const { t } = useTranslation();
  const startDate = new Date(item.start_time).toLocaleString();
  const endDate = new Date(item.end_time).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

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
        <div className="schedule-card__copy">
          <div className="meta-row">
            <span className="badge">{item.status}</span>
            {item.age_rating ? <span className="badge">{item.age_rating}</span> : null}
            <span className="badge">
              {item.available_seats} {t("seatsLeft")}
            </span>
          </div>
          <h3>{item.movie_title}</h3>
          <p className="muted">
            {startDate} | {t("endsAt")}: {endDate}
          </p>
        </div>
      </div>

      <div className="stats-row">
        <span className="badge">
          {t("price")}: {formatCurrency(item.price)}
        </span>
        <span className="badge">
          {item.available_seats}/{item.total_seats}
        </span>
        {item.genres.length > 0 ? <span className="badge">{item.genres.join(", ")}</span> : null}
      </div>

      <div className="schedule-card__footer">
        <p className="muted">{t("sessionCardHint")}</p>
        <Link to={`/schedule/${item.id}`} className="button">
          {t("viewSession")}
        </Link>
      </div>
    </article>
  );
}
