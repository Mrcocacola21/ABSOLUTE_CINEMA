import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "./ProfilePage.css";

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

type OrdersTab = "active" | "history";

const emptySensitiveFields = {
  password: "",
  current_password: "",
};

function getInitials(value: string): string {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "CS";
  }

  return parts
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

function isTicketUsable(ticket: OrderTicket): boolean {
  return ticket.valid_for_entry && ticket.status !== "cancelled" && !ticket.cancelled_at && !ticket.checked_in_at;
}

function getOrderUsableTickets(order: Order): OrderTicket[] {
  return order.tickets.filter(isTicketUsable);
}

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
  const [activeOrdersTab, setActiveOrdersTab] = useState<OrdersTab>("active");
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

    const normalizedName = form.name.trim().replace(/\s+/g, " ");
    const normalizedEmail = form.email.trim().toLowerCase();
    const payload: Record<string, string> = {};
    if (normalizedName !== currentUser.name) {
      payload.name = normalizedName;
    }
    if (normalizedEmail !== currentUser.email) {
      payload.email = normalizedEmail;
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

  const accountStatus = formatStateLabel(currentUser.is_active ? "active" : "inactive");
  const accountRole = formatStateLabel(currentUser.role);
  const profileInitials = getInitials(currentUser.name);
  const totalTicketsCount = orders.reduce((sum, order) => sum + order.tickets_count, 0);
  const usableTicketsCount = orders.reduce((sum, order) => sum + getOrderUsableTickets(order).length, 0);
  const activeOrders = orders.filter((order) => getOrderUsableTickets(order).length > 0);
  const visibleOrders = activeOrdersTab === "active" ? activeOrders : orders;
  const visibleTicketsCount = visibleOrders.reduce(
    (sum, order) => sum + (activeOrdersTab === "active" ? getOrderUsableTickets(order).length : order.tickets.length),
    0,
  );

  return (
    <div className="profile-page">
      <section className="panel profile-hero">
        <div className="profile-hero__main">
          <div className="profile-hero__avatar" aria-hidden="true">
            {profileInitials}
          </div>

          <div className="profile-hero__copy">
            <p className="page-eyebrow">{t("common.account.label")}</p>
            <h1 className="page-title profile-hero__title">{currentUser.name}</h1>
            <p className="profile-hero__subtitle">{t("profile.page.intro")}</p>

            <div className="profile-hero__meta">
              <div className="profile-hero__meta-card">
                <span>{t("common.labels.email")}</span>
                <strong title={currentUser.email}>{currentUser.email}</strong>
              </div>
              <div className="profile-hero__meta-card">
                <span>{t("common.account.label")}</span>
                <strong>{accountRole}</strong>
              </div>
              <div className="profile-hero__meta-card">
                <span>{t("common.labels.date")}</span>
                <strong>{formatDateTime(currentUser.created_at, i18n.language)}</strong>
              </div>
            </div>
          </div>
        </div>

        <aside className="profile-hero__aside">
          <div className="profile-hero__aside-head">
            <span className="badge">{accountStatus}</span>
            <p className="muted">{currentUser.email}</p>
          </div>

          <div className="profile-hero__summary">
            <div className="profile-hero__stat profile-hero__stat--primary">
              <span>{t("common.labels.status")}</span>
              <strong>{accountStatus}</strong>
              <p>{accountRole}</p>
            </div>

            <div className="profile-hero__stats">
              <div className="profile-hero__stat">
                <span>{t("profile.orders.title")}</span>
                <strong>{isOrdersLoading ? "..." : orders.length}</strong>
              </div>
              <div className="profile-hero__stat">
                <span>{t("common.labels.tickets")}</span>
                <strong>{isOrdersLoading ? "..." : totalTicketsCount}</strong>
              </div>
            </div>
          </div>
        </aside>
      </section>

      {feedback ? (
        <StatusBanner
          tone={feedback.tone}
          title={feedback.title}
          message={feedback.message}
        />
      ) : null}

      <section className="profile-layout">
        <form className="form-card profile-panel profile-form-panel" onSubmit={handleProfileUpdate}>
          <div className="profile-panel__header">
            <div className="profile-panel__copy">
              <h2 className="section-title">{t("profile.form.title")}</h2>
              <p className="profile-panel__summary">{t("profile.form.intro")}</p>
            </div>
            <span className="badge">{accountRole}</span>
          </div>

          <div className="profile-form__hint-card">
            <strong>{t("common.labels.currentPassword")}</strong>
            <p>{t("profile.form.requirementHint")}</p>
          </div>

          <div className="profile-form__grid">
            <label className="field">
              <span>{t("common.labels.name")}</span>
              <input
                required
                minLength={2}
                maxLength={255}
                pattern=".*\S.*"
                autoComplete="name"
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
                autoComplete="email"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.newPassword")}</span>
              <input
                minLength={8}
                maxLength={128}
                disabled={isSavingProfile || isDeactivatingAccount}
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>{t("common.labels.currentPassword")}</span>
              <input
                minLength={8}
                maxLength={128}
                disabled={isSavingProfile || isDeactivatingAccount}
                type="password"
                autoComplete="current-password"
                value={form.current_password}
                onChange={(event) =>
                  setForm((current) => ({ ...current, current_password: event.target.value }))
                }
              />
            </label>
          </div>

          <div className="profile-form__footer">
            <div className="profile-form__actions">
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
          </div>
        </form>

        <section className="form-card profile-panel profile-orders-panel">
          <div className="profile-panel__header profile-panel__header--orders">
            <div className="profile-panel__copy">
              <h2 className="section-title">{t("profile.orders.title")}</h2>
              <p className="profile-panel__summary">{t("profile.orders.intro")}</p>
            </div>

            <div className="profile-panel__actions">
              <span className="badge">{isOrdersLoading ? "..." : orders.length}</span>
              {!isOrdersLoading && orders.length > 0 ? (
                <span className="badge">
                  {t("profile.orders.activeSummary", {
                    active: usableTicketsCount,
                    total: totalTicketsCount,
                  })}
                </span>
              ) : null}
            </div>
          </div>

          {!isOrdersLoading && !ordersErrorMessage ? (
            <div className="profile-orders__tabs" role="tablist" aria-label={t("profile.orders.tabs.label")}>
              <button
                id="profile-orders-tab-active"
                className={`profile-orders__tab${activeOrdersTab === "active" ? " is-active" : ""}`}
                type="button"
                role="tab"
                aria-selected={activeOrdersTab === "active"}
                aria-controls="profile-orders-panel"
                onClick={() => setActiveOrdersTab("active")}
              >
                <span>{t("profile.orders.tabs.active")}</span>
                <strong>{usableTicketsCount}</strong>
              </button>
              <button
                id="profile-orders-tab-history"
                className={`profile-orders__tab${activeOrdersTab === "history" ? " is-active" : ""}`}
                type="button"
                role="tab"
                aria-selected={activeOrdersTab === "history"}
                aria-controls="profile-orders-panel"
                onClick={() => setActiveOrdersTab("history")}
              >
                <span>{t("profile.orders.tabs.history")}</span>
                <strong>{totalTicketsCount}</strong>
              </button>
            </div>
          ) : null}

          {isOrdersLoading ? (
            <section className="profile-orders__state profile-orders__state--loading" aria-busy="true">
              <div className="profile-orders__state-copy">
                <h3 className="section-title">{t("profile.orders.loadingTitle")}</h3>
                <p>{t("profile.orders.loadingMessage")}</p>
              </div>
            </section>
          ) : null}

          {!isOrdersLoading && ordersErrorMessage ? (
            <section className="profile-orders__state profile-orders__state--error">
              <div className="profile-orders__state-copy">
                <h3 className="section-title">{t("profile.orders.unavailableTitle")}</h3>
                <p>{ordersErrorMessage}</p>
              </div>

              <button className="button--ghost" type="button" onClick={() => void refreshOrders()}>
                {t("common.actions.retry")}
              </button>
            </section>
          ) : null}

          {!isOrdersLoading && !ordersErrorMessage && visibleOrders.length === 0 ? (
            <section
              id="profile-orders-panel"
              className="profile-orders__empty"
              role="tabpanel"
              aria-labelledby={
                activeOrdersTab === "active" ? "profile-orders-tab-active" : "profile-orders-tab-history"
              }
            >
              <span className="badge">
                {activeOrdersTab === "active"
                  ? t("profile.orders.tabs.active")
                  : t("profile.orders.tabs.history")}
              </span>

              <div className="profile-orders__empty-copy">
                <h3 className="section-title">
                  {activeOrdersTab === "active"
                    ? t("profile.orders.emptyActiveTitle")
                    : t("profile.orders.emptyHistoryTitle")}
                </h3>
                <p>
                  {activeOrdersTab === "active"
                    ? t("profile.orders.emptyActiveText")
                    : t("profile.orders.emptyHistoryText")}
                </p>
              </div>

              <Link to="/schedule" className="button">
                {t("common.actions.browseSchedule")}
              </Link>
            </section>
          ) : null}

          {!isOrdersLoading && !ordersErrorMessage && visibleOrders.length > 0 ? (
            <div
              id="profile-orders-panel"
              className="profile-orders__list"
              role="tabpanel"
              aria-labelledby={
                activeOrdersTab === "active" ? "profile-orders-tab-active" : "profile-orders-tab-history"
              }
            >
              <p className="profile-orders__tab-summary">
                {activeOrdersTab === "active"
                  ? t("profile.orders.activeTabSummary", {
                      orders: visibleOrders.length,
                      tickets: visibleTicketsCount,
                    })
                  : t("profile.orders.historyTabSummary", {
                      orders: visibleOrders.length,
                      tickets: visibleTicketsCount,
                    })}
              </p>

              {visibleOrders.map((order) => {
                const movieTitle = getLocalizedText(order.movie_title, i18n.language);
                const ticketsToShow = activeOrdersTab === "active" ? getOrderUsableTickets(order) : order.tickets;
                const usableTicketsInOrder = getOrderUsableTickets(order).length;
                const entrySummary =
                  usableTicketsInOrder > 0
                    ? t("profile.orders.usableSummary", { count: usableTicketsInOrder })
                    : order.checked_in_tickets_count > 0
                      ? t("profile.orders.usedSummary", { count: order.checked_in_tickets_count })
                      : t("profile.orders.usableSummary", { count: usableTicketsInOrder });

                return (
                  <article key={order.id} className="card order-history__order profile-order-card">
                    <div className="profile-order-card__hero">
                      <div className="media-tile profile-order-card__media" aria-hidden="true">
                        {order.poster_url ? (
                          <img src={order.poster_url} alt="" className="media-tile__image" />
                        ) : (
                          getInitials(movieTitle)
                        )}
                      </div>

                      <div className="profile-order-card__copy">
                        <div className="profile-order-card__headline">
                          <div>
                            <h3 className="profile-order-card__title">{movieTitle}</h3>
                            <p className="muted profile-order-card__session">
                              {formatDateTime(order.session_start_time, i18n.language)} |{" "}
                              {formatStateLabel(order.session_status)}
                            </p>
                          </div>
                          <span className="badge">{formatStateLabel(order.status)}</span>
                        </div>

                        <div className="order-history__meta">
                          <span className="badge">{t("profile.orders.shortId", { id: order.id.slice(-6) })}</span>
                          <span className="badge">
                            {t("profile.orders.ticketsCount", {
                              count: activeOrdersTab === "active" ? ticketsToShow.length : order.tickets_count,
                            })}
                          </span>
                          <span className="badge">
                            {entrySummary}
                          </span>
                          {order.age_rating ? <span className="badge">{order.age_rating}</span> : null}
                        </div>
                      </div>

                      <div className="profile-order-card__summary">
                        <div className="profile-order-card__price">
                          <span>{t("common.labels.total")}</span>
                          <strong>{formatCurrency(order.total_price, i18n.language)}</strong>
                        </div>

                        <Link to={`/me/orders/${order.id}`} className="button profile-order-card__cta">
                          {t("common.actions.viewDetails")}
                        </Link>
                        <Link to={`/schedule/${order.session_id}`} className="button--ghost profile-order-card__cta">
                          {t("common.actions.viewSession")}
                        </Link>
                      </div>
                    </div>

                    <div className="order-history__tickets">
                      {ticketsToShow.map((ticket) => (
                        <div key={ticket.id} className="order-history__ticket profile-order-ticket">
                          <div className="order-history__ticket-copy">
                            <strong>
                              {t("common.labels.seat")} {ticket.seat_row}-{ticket.seat_number}
                            </strong>
                            <p className="muted">
                              {t("profile.orders.purchasedAt", {
                                date: formatDateTime(ticket.purchased_at, i18n.language),
                              })}
                              {ticket.cancelled_at
                                ? ` | ${t("profile.orders.cancelledAt", {
                                    date: formatDateTime(ticket.cancelled_at, i18n.language),
                                  })}`
                                : ""}
                              {ticket.checked_in_at
                                ? ` | ${t("profile.orders.checkedInAt", {
                                    date: formatDateTime(ticket.checked_in_at, i18n.language),
                                  })}`
                                : ""}
                            </p>
                          </div>

                          <div className="profile-order-ticket__meta">
                            <span className="badge">{formatStateLabel(ticket.status)}</span>
                            {ticket.valid_for_entry ? (
                              <span className="badge badge--active">{t("profile.orders.validForEntry")}</span>
                            ) : null}
                            <span className="badge">{formatCurrency(ticket.price, i18n.language)}</span>
                            {ticket.is_cancellable ? (
                              <button
                                className="button--ghost profile-order-ticket__action"
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
                        </div>
                      ))}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </section>
      </section>
    </div>
  );
}
