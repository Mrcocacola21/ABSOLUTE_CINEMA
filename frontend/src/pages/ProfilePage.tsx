import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { cancelTicketRequest, listMyTicketsRequest } from "@/api/tickets";
import { deactivateCurrentUserRequest, updateCurrentUserRequest } from "@/api/users";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import type { TicketListItem } from "@/types/domain";

interface ProfileFormState {
  name: string;
  email: string;
  password: string;
  current_password: string;
}

const emptySensitiveFields = {
  password: "",
  current_password: "",
};

export function ProfilePage() {
  const { t } = useTranslation();
  const { currentUser, logout, refreshCurrentUser } = useAuth();
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [form, setForm] = useState<ProfileFormState>({
    name: "",
    email: "",
    ...emptySensitiveFields,
  });
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    setForm({
      name: currentUser.name,
      email: currentUser.email,
      ...emptySensitiveFields,
    });
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    void refreshTickets();
  }, [currentUser?.id]);

  async function refreshTickets() {
    try {
      const response = await listMyTicketsRequest();
      setTickets(response.data);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, "Tickets are currently unavailable."));
    }
  }

  async function handleProfileUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentUser) {
      return;
    }

    const payload: Record<string, string> = {};
    if (form.name !== currentUser.name) {
      payload.name = form.name;
    }
    if (form.email !== currentUser.email) {
      payload.email = form.email;
    }
    if (form.password) {
      payload.password = form.password;
    }
    if (form.current_password) {
      payload.current_password = form.current_password;
    }

    if (Object.keys(payload).length === 0) {
      setStatusMessage("Nothing changed.");
      return;
    }

    try {
      const response = await updateCurrentUserRequest(payload);
      setStatusMessage(response.message);
      setErrorMessage("");
      await refreshCurrentUser();
      setForm((current) => ({
        ...current,
        ...emptySensitiveFields,
      }));
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, "Profile update failed."));
    }
  }

  async function handleDeactivateAccount() {
    try {
      const response = await deactivateCurrentUserRequest();
      setStatusMessage(response.message);
      setErrorMessage("");
      logout();
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, "Account deactivation failed."));
    }
  }

  async function handleCancelTicket(ticketId: string) {
    try {
      const response = await cancelTicketRequest(ticketId);
      setStatusMessage(response.message);
      setErrorMessage("");
      await refreshTickets();
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, "Ticket cancellation failed."));
    }
  }

  return (
    <>
      <section className="panel">
        <h1 className="page-title">{t("profile")}</h1>
        {!currentUser ? <p className="muted">{t("profileLoading")}</p> : null}
        {currentUser ? (
          <div className="stats-row">
            <span className="badge">{currentUser.name}</span>
            <span className="badge">{currentUser.email}</span>
            <span className="badge">{currentUser.role}</span>
            <span className="badge">{currentUser.is_active ? "active" : "inactive"}</span>
          </div>
        ) : null}
        {statusMessage ? <p className="badge">{statusMessage}</p> : null}
        {errorMessage ? <p className="badge badge--danger">{errorMessage}</p> : null}
      </section>

      {currentUser ? (
        <section className="split-grid">
          <form className="form-card" onSubmit={handleProfileUpdate}>
            <h3>Edit profile</h3>
            <div className="form-grid">
              <label className="field">
                <span>Name</span>
                <input
                  required
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  required
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>New password</span>
                <input
                  minLength={8}
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Current password</span>
                <input
                  minLength={8}
                  type="password"
                  value={form.current_password}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, current_password: event.target.value }))
                  }
                />
              </label>
            </div>
            <div className="actions-row">
              <button className="button" type="submit">
                Save profile
              </button>
              <button className="button--danger" type="button" onClick={handleDeactivateAccount}>
                Deactivate account
              </button>
            </div>
            <p className="muted">Changing email or password requires your current password.</p>
          </form>

          <section className="form-card">
            <h3>My tickets</h3>
            <div className="list">
              {tickets.map((ticket) => (
                <article key={ticket.id} className="card">
                  <strong>{ticket.movie_title}</strong>
                  <p className="muted">
                    {new Date(ticket.session_start_time).toLocaleString()} | seat {ticket.seat_row}-{ticket.seat_number}
                  </p>
                  <div className="stats-row">
                    <span className="badge">{ticket.status}</span>
                    <span className="badge">{ticket.session_status}</span>
                    <span className="badge">{ticket.price}</span>
                  </div>
                  {ticket.is_cancellable ? (
                    <button
                      className="button--ghost"
                      type="button"
                      onClick={() => {
                        void handleCancelTicket(ticket.id);
                      }}
                    >
                      Cancel ticket
                    </button>
                  ) : null}
                </article>
              ))}
              {tickets.length === 0 ? <p className="empty-state">You have no tickets yet.</p> : null}
            </div>
          </section>
        </section>
      ) : null}
    </>
  );
}
