import { useTranslation } from "react-i18next";

import type { AttendanceReport } from "@/types/domain";

interface AttendancePanelProps {
  report: AttendanceReport | null;
}

export function AttendancePanel({ report }: AttendancePanelProps) {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <h3>{t("attendanceOverview")}</h3>
      {!report ? <p className="muted">{t("loadAttendanceHint")}</p> : null}
      {report ? (
        <>
          <div className="stats-row">
            <span className="badge">
              {t("sessionsCount")}: {report.total_sessions}
            </span>
            <span className="badge">
              {t("ticketsSold")}: {report.total_tickets_sold}
            </span>
            <span className="badge">
              {t("generated")}: {new Date(report.generated_at).toLocaleString()}
            </span>
          </div>
          <div className="list">
            {report.sessions.map((item) => (
              <article key={item.session_id} className="card">
                <strong>{item.movie_title}</strong>
                <p className="muted">{new Date(item.start_time).toLocaleString()}</p>
                <div className="stats-row">
                  <span className="badge">
                    {item.tickets_sold}/{item.total_seats}
                  </span>
                  <span className="badge">
                    {(item.attendance_rate * 100).toFixed(0)}%
                  </span>
                  <span className="badge">{item.status}</span>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
