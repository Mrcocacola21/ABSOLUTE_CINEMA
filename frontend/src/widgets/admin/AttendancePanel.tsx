import { useTranslation } from "react-i18next";

import { getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { AttendanceReport, TicketListItem, User } from "@/types/domain";

interface AttendancePanelProps {
  report: AttendanceReport | null;
  tickets: TicketListItem[];
  users: User[];
}

export function AttendancePanel({ report, tickets, users }: AttendancePanelProps) {
  const { t, i18n } = useTranslation();
  const recentTickets = [...tickets]
    .sort((left, right) => new Date(right.purchased_at).getTime() - new Date(left.purchased_at).getTime())
    .slice(0, 6);
  const recentUsers = [...users]
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
    .slice(0, 6);
  const activeUsers = users.filter((user) => user.is_active).length;

  return (
    <section className="panel admin-reports">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">{t("admin.reports.eyebrow")}</p>
          <h2 className="section-title">{t("admin.reports.title")}</h2>
          <p className="muted">{t("admin.reports.intro")}</p>
        </div>
        {report ? <span className="badge">{report.total_sessions} {t("common.stats.sessionsTracked")}</span> : null}
      </div>

      {!report ? (
        <StatePanel
          tone="loading"
          title={t("admin.reports.loadingTitle")}
          message={t("admin.reports.loadingMessage")}
        />
      ) : (
        <>
          <div className="cards-grid admin-report-summary">
            <article className="card admin-report-summary__card">
              <strong>{report.total_sessions}</strong>
              <p className="muted">{t("admin.reports.summary.sessionsInReport")}</p>
            </article>
            <article className="card admin-report-summary__card">
              <strong>{report.total_tickets_sold}</strong>
              <p className="muted">{t("admin.reports.summary.ticketsSold")}</p>
            </article>
            <article className="card admin-report-summary__card">
              <strong>{activeUsers}</strong>
              <p className="muted">{t("admin.reports.summary.activeAccounts")}</p>
            </article>
            <article className="card admin-report-summary__card">
              <strong>{formatDateTime(report.generated_at)}</strong>
              <p className="muted">{t("admin.reports.summary.lastRefresh")}</p>
            </article>
          </div>

          <div className="admin-reports__grid">
            <section className="card admin-report-panel">
              <div className="admin-section__header">
                <div>
                  <p className="page-eyebrow">{t("admin.reports.attendance.eyebrow")}</p>
                  <h3 className="section-title">{t("admin.reports.attendance.title")}</h3>
                </div>
                <span className="badge">{report.sessions.length}</span>
              </div>

              {report.sessions.length > 0 ? (
                <div className="list">
                  {report.sessions.map((item) => (
                    <article key={item.session_id} className="admin-report-feed__item">
                      <div>
                        <strong>{getLocalizedText(item.movie_title, i18n.language)}</strong>
                        <p className="muted">{formatDateTime(item.start_time)}</p>
                      </div>
                      <div className="stats-row">
                        <span className="badge">
                          {item.tickets_sold}/{item.total_seats}
                        </span>
                        <span className="badge">
                          {(item.attendance_rate * 100).toFixed(0)}%
                        </span>
                        <span className="badge">{formatStateLabel(item.status)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <section className="empty-state empty-state--panel">
                  <h2>{t("admin.reports.attendance.emptyTitle")}</h2>
                  <p>{t("admin.reports.attendance.emptyText")}</p>
                </section>
              )}
            </section>

            <section className="card admin-report-panel">
              <div className="admin-section__header">
                <div>
                  <p className="page-eyebrow">{t("admin.reports.bookings.eyebrow")}</p>
                  <h3 className="section-title">{t("admin.reports.bookings.title")}</h3>
                </div>
                <span className="badge">{recentTickets.length}</span>
              </div>

              {recentTickets.length > 0 ? (
                <div className="list">
                  {recentTickets.map((ticket) => (
                    <article key={ticket.id} className="admin-report-feed__item">
                      <div>
                        <strong>{getLocalizedText(ticket.movie_title, i18n.language)}</strong>
                        <p className="muted">
                          {formatDateTime(ticket.session_start_time)} |{" "}
                          {t("admin.reports.bookingSeat", { seat: `${ticket.seat_row}-${ticket.seat_number}` })}
                        </p>
                      </div>
                      <div className="stats-row">
                        <span className="badge">{formatStateLabel(ticket.status)}</span>
                        <span className="badge">{formatStateLabel(ticket.session_status)}</span>
                        <span className="badge">{formatCurrency(ticket.price)}</span>
                        {ticket.user_name ? <span className="badge">{ticket.user_name}</span> : null}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <section className="empty-state empty-state--panel">
                  <h2>{t("admin.reports.bookings.emptyTitle")}</h2>
                  <p>{t("admin.reports.bookings.emptyText")}</p>
                </section>
              )}
            </section>

            <section className="card admin-report-panel">
              <div className="admin-section__header">
                <div>
                  <p className="page-eyebrow">{t("admin.reports.accounts.eyebrow")}</p>
                  <h3 className="section-title">{t("admin.reports.accounts.title")}</h3>
                </div>
                <span className="badge">{recentUsers.length}</span>
              </div>

              {recentUsers.length > 0 ? (
                <div className="list">
                  {recentUsers.map((user) => (
                    <article key={user.id} className="admin-report-feed__item">
                      <div>
                        <strong>{user.name}</strong>
                        <p className="muted">{user.email}</p>
                      </div>
                      <div className="stats-row">
                        <span className="badge">{formatStateLabel(user.role)}</span>
                        <span className="badge">
                          {user.is_active ? t("common.states.activeAccount") : t("common.states.inactiveAccount")}
                        </span>
                        <span className="badge">{formatDateTime(user.created_at)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <section className="empty-state empty-state--panel">
                  <h2>{t("admin.reports.accounts.emptyTitle")}</h2>
                  <p>{t("admin.reports.accounts.emptyText")}</p>
                </section>
              )}
            </section>
          </div>
        </>
      )}
    </section>
  );
}
