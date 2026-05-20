import { useTranslation } from "react-i18next";

import { ScheduleCard } from "@/entities/schedule/ScheduleCard";
import type { ScheduleItem } from "@/types/domain";

interface ScheduleListProps {
  items: ScheduleItem[];
}

export function ScheduleList({ items }: ScheduleListProps) {
  const { t } = useTranslation();

  if (items.length === 0) {
    return (
      <section className="empty-state empty-state--panel empty-state--compact">
        <h2>{t("schedule.list.noMatchingTitle")}</h2>
        <p>{t("schedule.list.noMatchingText")}</p>
      </section>
    );
  }

  return (
    <section className="list schedule-list">
      {items.map((item) => (
        <ScheduleCard key={item.id} item={item} />
      ))}
    </section>
  );
}
