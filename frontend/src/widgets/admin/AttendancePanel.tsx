import { useTranslation } from "react-i18next";

import type { AttendanceReport } from "@/types/domain";

interface AttendancePanelProps {
  report: AttendanceReport | null;
}

export function AttendancePanel({ report }: AttendancePanelProps) {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">{t("attendance")}</p>
          <h3 className="section-title">{t("attendanceOverview")}</h3>
        </div>
        {report ? <span className="badge">{report.total_sessions}</span> : null}
      </div>
      {!report ? <p className="muted">{t("loadAttendanceHint")}</p> : null}
      {report ? (
        <>
          <div className="cards-grid admin-secondary-grid">
            <article className="card admin-card">
              <strong>{report.total_sessions}</strong>
              <p className="muted">{t("sessionsCount")}</p>
            </article>
            <article className="card admin-card">
              <strong>{report.total_tickets_sold}</strong>
              <p className="muted">{t("ticketsSold")}</p>
            </article>
            <article className="card admin-card">
              <strong>{new Date(report.generated_at).toLocaleString()}</strong>
              <p className="muted">{t("generated")}</p>
            </article>
          </div>
          <div className="list">
            {report.sessions.map((item) => (
              <article key={item.session_id} className="card admin-card">
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
