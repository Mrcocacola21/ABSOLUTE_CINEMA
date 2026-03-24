import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { AttendanceReport, TicketListItem, User } from "@/types/domain";

interface AttendancePanelProps {
  report: AttendanceReport | null;
  tickets: TicketListItem[];
  users: User[];
}

export function AttendancePanel({ report, tickets, users }: AttendancePanelProps) {
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
          <p className="page-eyebrow">Reports / Attendance</p>
          <h2 className="section-title">Attendance and activity overview</h2>
          <p className="muted">
            Review session performance, latest bookings, and recent account activity in one place.
          </p>
        </div>
        {report ? <span className="badge">{report.total_sessions} sessions tracked</span> : null}
      </div>

      {!report ? (
        <StatePanel
          tone="loading"
          title="Loading reports"
          message="Fetching attendance, bookings, and user activity."
        />
      ) : (
        <>
          <div className="cards-grid admin-report-summary">
            <article className="card admin-report-summary__card">
              <strong>{report.total_sessions}</strong>
              <p className="muted">Sessions in the report</p>
            </article>
            <article className="card admin-report-summary__card">
              <strong>{report.total_tickets_sold}</strong>
              <p className="muted">Tickets sold</p>
            </article>
            <article className="card admin-report-summary__card">
              <strong>{activeUsers}</strong>
              <p className="muted">Active accounts</p>
            </article>
            <article className="card admin-report-summary__card">
              <strong>{formatDateTime(report.generated_at)}</strong>
              <p className="muted">Last report refresh</p>
            </article>
          </div>

          <div className="admin-reports__grid">
            <section className="card admin-report-panel">
              <div className="admin-section__header">
                <div>
                  <p className="page-eyebrow">Attendance</p>
                  <h3 className="section-title">Session performance</h3>
                </div>
                <span className="badge">{report.sessions.length}</span>
              </div>

              {report.sessions.length > 0 ? (
                <div className="list">
                  {report.sessions.map((item) => (
                    <article key={item.session_id} className="admin-report-feed__item">
                      <div>
                        <strong>{item.movie_title}</strong>
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
                  <h2>No attendance data yet</h2>
                  <p>Attendance summaries appear after sessions are created and tickets start selling.</p>
                </section>
              )}
            </section>

            <section className="card admin-report-panel">
              <div className="admin-section__header">
                <div>
                  <p className="page-eyebrow">Bookings</p>
                  <h3 className="section-title">Recent ticket activity</h3>
                </div>
                <span className="badge">{recentTickets.length}</span>
              </div>

              {recentTickets.length > 0 ? (
                <div className="list">
                  {recentTickets.map((ticket) => (
                    <article key={ticket.id} className="admin-report-feed__item">
                      <div>
                        <strong>{ticket.movie_title}</strong>
                        <p className="muted">
                          {formatDateTime(ticket.session_start_time)} | Seat {ticket.seat_row}-{ticket.seat_number}
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
                  <h2>No ticket activity yet</h2>
                  <p>Recent bookings will appear here once customers start reserving seats.</p>
                </section>
              )}
            </section>

            <section className="card admin-report-panel">
              <div className="admin-section__header">
                <div>
                  <p className="page-eyebrow">Accounts</p>
                  <h3 className="section-title">Newest users</h3>
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
                          {user.is_active ? "Active account" : "Inactive account"}
                        </span>
                        <span className="badge">{formatDateTime(user.created_at)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <section className="empty-state empty-state--panel">
                  <h2>No registered users yet</h2>
                  <p>User registrations will appear here after accounts are created.</p>
                </section>
              )}
            </section>
          </div>
        </>
      )}
    </section>
  );
}
