import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { listMyOrdersRequest } from "@/api/orders";
import { cancelTicketRequest } from "@/api/tickets";
import { deactivateCurrentUserRequest, updateCurrentUserRequest } from "@/api/users";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { Order, OrderTicket } from "@/types/domain";

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
  const { currentUser, isAuthLoading, logout, refreshCurrentUser } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [form, setForm] = useState<ProfileFormState>({
    name: "",
    email: "",
    ...emptySensitiveFields,
  });
  const [ordersErrorMessage, setOrdersErrorMessage] = useState("");
  const [isOrdersLoading, setIsOrdersLoading] = useState(true);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isDeactivatingAccount, setIsDeactivatingAccount] = useState(false);
  const [cancellingTicketId, setCancellingTicketId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error" | "info";
    title?: string;
    message: string;
  } | null>(null);

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
      setOrders([]);
      setIsOrdersLoading(false);
      return;
    }
    void refreshOrders();
  }, [currentUser?.id]);

  async function refreshOrders(options?: { background?: boolean }) {
    const background = options?.background ?? false;
    if (!background) {
      setIsOrdersLoading(true);
    }

    try {
      const response = await listMyOrdersRequest();
      setOrders(response.data);
      setOrdersErrorMessage("");
    } catch (error) {
      setOrders([]);
      setOrdersErrorMessage(extractApiErrorMessage(error, "Orders are currently unavailable."));
    } finally {
      if (!background) {
        setIsOrdersLoading(false);
      }
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
      setFeedback({
        tone: "info",
        message: "There are no profile changes to save.",
      });
      return;
    }

    setIsSavingProfile(true);
    setFeedback(null);
    try {
      const response = await updateCurrentUserRequest(payload);
      await refreshCurrentUser();
      setFeedback({
        tone: "success",
        title: "Profile updated",
        message: response.message,
      });
      setForm((current) => ({
        ...current,
        ...emptySensitiveFields,
      }));
    } catch (error) {
      setFeedback({
        tone: "error",
        title: "Profile update failed",
        message: extractApiErrorMessage(error, "Profile update failed."),
      });
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleDeactivateAccount() {
    const confirmed = window.confirm(
      "Deactivate this account? You will be signed out immediately after the request succeeds.",
    );
    if (!confirmed) {
      return;
    }

    setIsDeactivatingAccount(true);
    setFeedback(null);
    try {
      const response = await deactivateCurrentUserRequest();
      setFeedback({
        tone: "success",
        title: "Account deactivated",
        message: response.message,
      });
      logout();
    } catch (error) {
      setFeedback({
        tone: "error",
        title: "Account deactivation failed",
        message: extractApiErrorMessage(error, "Account deactivation failed."),
      });
    } finally {
      setIsDeactivatingAccount(false);
    }
  }

  async function handleCancelTicket(order: Order, ticket: OrderTicket) {
    const confirmed = window.confirm(
      `Cancel the ticket for ${order.movie_title} at seat ${ticket.seat_row}-${ticket.seat_number}?`,
    );
    if (!confirmed) {
      return;
    }

    setCancellingTicketId(ticket.id);
    setFeedback(null);
    try {
      const response = await cancelTicketRequest(ticket.id);
      await refreshOrders({ background: true });
      setFeedback({
        tone: "success",
        title: "Ticket cancelled",
        message: `${response.message} Order ${order.id} was refreshed.`,
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: "Ticket cancellation failed",
        message: extractApiErrorMessage(error, "Ticket cancellation failed."),
      });
    } finally {
      setCancellingTicketId(null);
    }
  }

  if (isAuthLoading && !currentUser) {
    return (
      <StatePanel
        tone="loading"
        title="Loading your profile"
        message="Fetching your account details and ticket history."
      />
    );
  }

  if (!currentUser) {
    return (
      <StatePanel
        tone="error"
        title="Profile is unavailable"
        message="Your account details could not be loaded."
        action={
          <Link to="/login" className="button--ghost">
            Sign in again
          </Link>
        }
      />
    );
  }

  return (
    <>
      <section className="panel">
        <h1 className="page-title">{t("profile")}</h1>
        <p className="muted">Manage your account details and ticket activity in one place.</p>
        <div className="stats-row">
          <span className="badge">{currentUser.name}</span>
          <span className="badge">{currentUser.email}</span>
          <span className="badge">{formatStateLabel(currentUser.role)}</span>
          <span className="badge">
            {formatStateLabel(currentUser.is_active ? "active" : "inactive")}
          </span>
        </div>
      </section>

      {feedback ? (
        <StatusBanner
          tone={feedback.tone}
          title={feedback.title}
          message={feedback.message}
        />
      ) : null}

      <section className="split-grid">
        <form className="form-card" onSubmit={handleProfileUpdate}>
          <div className="toolbar-panel__header">
            <div>
              <h3>Edit profile</h3>
              <p className="muted">Update your name, email, or password.</p>
            </div>
          </div>
          <div className="form-grid">
            <label className="field">
              <span>Name</span>
              <input
                required
                disabled={isSavingProfile || isDeactivatingAccount}
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Email</span>
              <input
                required
                disabled={isSavingProfile || isDeactivatingAccount}
                type="email"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>New password</span>
              <input
                minLength={8}
                disabled={isSavingProfile || isDeactivatingAccount}
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Current password</span>
              <input
                minLength={8}
                disabled={isSavingProfile || isDeactivatingAccount}
                type="password"
                value={form.current_password}
                onChange={(event) =>
                  setForm((current) => ({ ...current, current_password: event.target.value }))
                }
              />
            </label>
          </div>
          <div className="actions-row">
            <button className="button" type="submit" disabled={isSavingProfile || isDeactivatingAccount}>
              {isSavingProfile ? "Saving changes..." : "Save changes"}
            </button>
            <button
              className="button--danger"
              type="button"
              disabled={isSavingProfile || isDeactivatingAccount}
              onClick={() => {
                void handleDeactivateAccount();
              }}
            >
              {isDeactivatingAccount ? "Deactivating..." : "Deactivate account"}
            </button>
          </div>
          <p className="muted">Changing your email or password requires the current password.</p>
        </form>

        <section className="form-card">
          <div className="admin-section__header">
            <div>
              <h3>My orders</h3>
              <p className="muted">Review grouped purchases, inspect seats, and cancel eligible tickets.</p>
            </div>
            <span className="badge">{orders.length}</span>
          </div>

          {isOrdersLoading ? (
            <StatePanel
              tone="loading"
              title="Loading your orders"
              message="Fetching your latest grouped purchases."
            />
          ) : null}

          {!isOrdersLoading && ordersErrorMessage ? (
            <StatePanel
              tone="error"
              title="Unable to load your orders"
              message={ordersErrorMessage}
              action={
                <button className="button--ghost" type="button" onClick={() => void refreshOrders()}>
                  Try again
                </button>
              }
            />
          ) : null}

          {!isOrdersLoading && !ordersErrorMessage && orders.length === 0 ? (
            <section className="empty-state empty-state--panel">
              <h2>No orders yet</h2>
              <p>Once you purchase one or more seats for a session, the grouped order will appear here.</p>
              <Link to="/schedule" className="button--ghost">
                Browse schedule
              </Link>
            </section>
          ) : null}

          {!isOrdersLoading && !ordersErrorMessage && orders.length > 0 ? (
            <div className="list">
              {orders.map((order) => (
                <article key={order.id} className="card order-history__order">
                  <div className="order-history__order-head">
                    <div>
                      <strong>{order.movie_title}</strong>
                      <p className="muted">
                        {formatDateTime(order.session_start_time)} | {formatStateLabel(order.session_status)}
                      </p>
                    </div>
                    <div className="stats-row">
                      <span className="badge">{formatStateLabel(order.status)}</span>
                      <span className="badge">
                        {order.active_tickets_count}/{order.tickets_count} active
                      </span>
                      <span className="badge">{formatCurrency(order.total_price)}</span>
                    </div>
                  </div>

                  <div className="order-history__meta">
                    <span className="badge">Order {order.id.slice(-6)}</span>
                    <span className="badge">
                      {order.tickets_count} ticket{order.tickets_count > 1 ? "s" : ""}
                    </span>
                    {order.age_rating ? <span className="badge">{order.age_rating}</span> : null}
                  </div>

                  <div className="order-history__tickets">
                    {order.tickets.map((ticket) => (
                      <div key={ticket.id} className="order-history__ticket">
                        <div className="order-history__ticket-copy">
                          <strong>
                            Seat {ticket.seat_row}-{ticket.seat_number}
                          </strong>
                          <p className="muted">
                            Purchased {formatDateTime(ticket.purchased_at)}
                            {ticket.cancelled_at ? ` | Cancelled ${formatDateTime(ticket.cancelled_at)}` : ""}
                          </p>
                        </div>
                        <div className="stats-row">
                          <span className="badge">{formatStateLabel(ticket.status)}</span>
                          <span className="badge">{formatCurrency(ticket.price)}</span>
                        </div>
                        {ticket.is_cancellable ? (
                          <button
                            className="button--ghost"
                            type="button"
                            disabled={cancellingTicketId === ticket.id}
                            onClick={() => {
                              void handleCancelTicket(order, ticket);
                            }}
                          >
                            {cancellingTicketId === ticket.id ? "Cancelling..." : "Cancel ticket"}
                          </button>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </section>
      </section>
    </>
  );
}
