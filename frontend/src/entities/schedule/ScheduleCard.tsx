import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { ScheduleItem } from "@/types/domain";

interface ScheduleCardProps {
  item: ScheduleItem;
}

export function ScheduleCard({ item }: ScheduleCardProps) {
  const { t } = useTranslation();
  const startDate = new Date(item.start_time).toLocaleString();

  return (
    <article className="card schedule-card">
      <div className="meta-row">
        <span className="badge">{item.status}</span>
        {item.age_rating ? <span className="badge">{item.age_rating}</span> : null}
        <span className="badge">
          {item.available_seats} {t("seatsLeft")}
        </span>
      </div>
      <div>
        <h3>{item.movie_title}</h3>
        <p className="muted">{startDate}</p>
      </div>
      <div className="stats-row">
        <span className="badge">
          {t("price")}: {item.price}
        </span>
        <span className="badge">
          {item.available_seats}/{item.total_seats}
        </span>
        {item.genres.length > 0 ? <span className="badge">{item.genres.join(", ")}</span> : null}
      </div>
      <Link to={`/schedule/${item.id}`} className="button">
        {t("viewSession")}
      </Link>
    </article>
  );
}
