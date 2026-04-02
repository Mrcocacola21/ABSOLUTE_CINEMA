import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { listMyOrdersRequest } from "@/api/orders";
import { cancelTicketRequest } from "@/api/tickets";
import { deactivateCurrentUserRequest, updateCurrentUserRequest } from "@/api/users";
import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
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
  const { t, i18n } = useTranslation();
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
      setOrdersErrorMessage(extractApiErrorMessage(error, t("profile.orders.unavailableMessage")));
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
        message: t("profile.form.noChanges"),
      });
      return;
    }

    setIsSavingProfile(true);
    setFeedback(null);
    try {
      await updateCurrentUserRequest(payload);
      await refreshCurrentUser();
      setFeedback({
        tone: "success",
        title: t("profile.form.updatedTitle"),
        message: t("profile.form.updatedMessage"),
      });
      setForm((current) => ({
        ...current,
        ...emptySensitiveFields,
      }));
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("profile.form.updateFailedTitle"),
        message: extractApiErrorMessage(error, t("profile.form.updateFailedMessage")),
      });
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleDeactivateAccount() {
    const confirmed = window.confirm(t("profile.form.deactivateConfirm"));
    if (!confirmed) {
      return;
    }

    setIsDeactivatingAccount(true);
    setFeedback(null);
    try {
      await deactivateCurrentUserRequest();
      setFeedback({
        tone: "success",
        title: t("profile.form.deactivatedTitle"),
        message: t("profile.form.deactivatedMessage"),
      });
      logout();
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("profile.form.deactivationFailedTitle"),
        message: extractApiErrorMessage(error, t("profile.form.deactivationFailedMessage")),
      });
    } finally {
      setIsDeactivatingAccount(false);
    }
  }

  async function handleCancelTicket(order: Order, ticket: OrderTicket) {
    const movieTitle = getLocalizedText(order.movie_title, i18n.language);
    const confirmed = window.confirm(
      t("profile.orders.cancelConfirm", {
        movie: movieTitle,
        seat: `${ticket.seat_row}-${ticket.seat_number}`,
      }),
    );
    if (!confirmed) {
      return;
    }

    setCancellingTicketId(ticket.id);
    setFeedback(null);
    try {
      await cancelTicketRequest(ticket.id);
      await refreshOrders({ background: true });
      setFeedback({
        tone: "success",
        title: t("profile.orders.cancelSuccessTitle"),
        message: t("profile.orders.cancelSuccessMessage"),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("profile.orders.cancelFailedTitle"),
        message: extractApiErrorMessage(error, t("profile.orders.cancelFailedMessage")),
      });
    } finally {
      setCancellingTicketId(null);
    }
  }

  if (isAuthLoading && !currentUser) {
    return (
      <StatePanel
        tone="loading"
        title={t("profile.page.loadingTitle")}
        message={t("profile.page.loadingMessage")}
      />
    );
  }

  if (!currentUser) {
    return (
      <StatePanel
        tone="error"
        title={t("profile.page.unavailableTitle")}
        message={t("profile.page.unavailableMessage")}
        action={
          <Link to="/login" className="button--ghost">
            {t("common.actions.signInAgain")}
          </Link>
        }
      />
    );
  }

  return (
    <>
      <section className="panel">
        <h1 className="page-title">{t("profile.page.title")}</h1>
        <p className="muted">{t("profile.page.intro")}</p>
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
              <h3>{t("profile.form.title")}</h3>
              <p className="muted">{t("profile.form.intro")}</p>
            </div>
          </div>
          <div className="form-grid">
            <label className="field">
              <span>{t("common.labels.name")}</span>
              <input
                required
                disabled={isSavingProfile || isDeactivatingAccount}
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.email")}</span>
              <input
                required
                disabled={isSavingProfile || isDeactivatingAccount}
                type="email"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.newPassword")}</span>
              <input
                minLength={8}
                disabled={isSavingProfile || isDeactivatingAccount}
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.currentPassword")}</span>
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
              {isSavingProfile ? t("profile.form.saveLoading") : t("profile.form.saveIdle")}
            </button>
            <button
              className="button--danger"
              type="button"
              disabled={isSavingProfile || isDeactivatingAccount}
              onClick={() => {
                void handleDeactivateAccount();
              }}
            >
              {isDeactivatingAccount ? t("profile.form.deactivating") : t("common.actions.deactivateAccount")}
            </button>
          </div>
          <p className="muted">{t("profile.form.requirementHint")}</p>
        </form>

        <section className="form-card">
          <div className="admin-section__header">
            <div>
              <h3>{t("profile.orders.title")}</h3>
              <p className="muted">{t("profile.orders.intro")}</p>
            </div>
            <span className="badge">{orders.length}</span>
          </div>

          {isOrdersLoading ? (
            <StatePanel
              tone="loading"
              title={t("profile.orders.loadingTitle")}
              message={t("profile.orders.loadingMessage")}
            />
          ) : null}

          {!isOrdersLoading && ordersErrorMessage ? (
            <StatePanel
              tone="error"
              title={t("profile.orders.unavailableTitle")}
              message={ordersErrorMessage}
              action={
                <button className="button--ghost" type="button" onClick={() => void refreshOrders()}>
                  {t("common.actions.retry")}
                </button>
              }
            />
          ) : null}

          {!isOrdersLoading && !ordersErrorMessage && orders.length === 0 ? (
            <section className="empty-state empty-state--panel">
              <h2>{t("profile.orders.emptyTitle")}</h2>
              <p>{t("profile.orders.emptyText")}</p>
              <Link to="/schedule" className="button--ghost">
                {t("common.actions.browseSchedule")}
              </Link>
            </section>
          ) : null}

          {!isOrdersLoading && !ordersErrorMessage && orders.length > 0 ? (
            <div className="list">
              {orders.map((order) => (
                <article key={order.id} className="card order-history__order">
                  <div className="order-history__order-head">
                    <div>
                      <strong>{getLocalizedText(order.movie_title, i18n.language)}</strong>
                      <p className="muted">
                        {formatDateTime(order.session_start_time)} | {formatStateLabel(order.session_status)}
                      </p>
                    </div>
                    <div className="stats-row">
                      <span className="badge">{formatStateLabel(order.status)}</span>
                      <span className="badge">
                        {t("profile.orders.activeSummary", {
                          active: order.active_tickets_count,
                          total: order.tickets_count,
                        })}
                      </span>
                      <span className="badge">{formatCurrency(order.total_price)}</span>
                    </div>
                  </div>

                  <div className="order-history__meta">
                    <span className="badge">{t("profile.orders.shortId", { id: order.id.slice(-6) })}</span>
                    <span className="badge">{t("profile.orders.ticketsCount", { count: order.tickets_count })}</span>
                    {order.age_rating ? <span className="badge">{order.age_rating}</span> : null}
                  </div>

                  <div className="order-history__tickets">
                    {order.tickets.map((ticket) => (
                      <div key={ticket.id} className="order-history__ticket">
                        <div className="order-history__ticket-copy">
                          <strong>
                            {t("common.labels.seat")} {ticket.seat_row}-{ticket.seat_number}
                          </strong>
                          <p className="muted">
                            {t("profile.orders.purchasedAt", { date: formatDateTime(ticket.purchased_at) })}
                            {ticket.cancelled_at
                              ? ` | ${t("profile.orders.cancelledAt", {
                                  date: formatDateTime(ticket.cancelled_at),
                                })}`
                              : ""}
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
                            {cancellingTicketId === ticket.id
                              ? t("profile.orders.cancelLoading")
                              : t("common.actions.cancelTicket")}
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
