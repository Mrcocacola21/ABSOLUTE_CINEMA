import { Children, type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createAdminPaymentRefundRequest,
  getAdminPaymentDetailsRequest,
  getAdminPaymentReportRequest,
  listAdminPaymentsRequest,
  type AdminPaymentFilters,
  type AdminPaymentReportFilters,
} from "@/api/admin";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getIntlLocale, getLocalizedText } from "@/shared/localization";
import { formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type {
  AdminPaymentDetails,
  AdminPaymentListItem,
  PaymentReport,
  PaymentReportMovieAggregate,
  PaymentReportSessionAggregate,
  PaymentStatus,
  RefundStatus,
} from "@/types/domain";

import "./AdminPaymentsPage.css";

type FilterDraft = {
  status: string;
  provider: string;
  refundStatus: string;
  search: string;
};

type Feedback = {
  tone: "success" | "error" | "warning" | "info";
  title: string;
  message: string;
};

type ReportPreset = "today" | "7d" | "30d" | "month" | "all" | "custom";

type ReportPeriodDraft = {
  preset: ReportPreset;
  dateFrom: string;
  dateTo: string;
};

const PAYMENT_STATUS_OPTIONS: PaymentStatus[] = [
  "created",
  "pending",
  "requires_action",
  "succeeded",
  "failed",
  "cancelled",
  "expired",
  "partially_refunded",
  "refunded",
];

const REFUND_STATUS_OPTIONS: RefundStatus[] = ["created", "pending", "succeeded", "failed", "cancelled"];
const REPORT_PRESETS: ReportPreset[] = ["today", "7d", "30d", "month", "all"];

const DEFAULT_FILTERS: FilterDraft = {
  status: "",
  provider: "",
  refundStatus: "",
  search: "",
};

function buildAdminPaymentFilters(filters: FilterDraft): AdminPaymentFilters {
  return {
    limit: 100,
    status: filters.status || undefined,
    provider: filters.provider.trim() || undefined,
    refund_status: filters.refundStatus || undefined,
    search: filters.search.trim() || undefined,
  };
}

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfLocalDayIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 0, 0, 0, 0).toISOString();
}

function endOfLocalDayIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 23, 59, 59, 999).toISOString();
}

function createReportPeriod(preset: ReportPreset): ReportPeriodDraft {
  const now = new Date();
  if (preset === "all") {
    return { preset, dateFrom: "", dateTo: "" };
  }

  const start = new Date(now);
  if (preset === "today") {
    start.setHours(0, 0, 0, 0);
  } else if (preset === "7d") {
    start.setDate(now.getDate() - 6);
  } else if (preset === "month") {
    start.setDate(1);
  } else {
    start.setDate(now.getDate() - 29);
  }

  return {
    preset,
    dateFrom: toDateInputValue(start),
    dateTo: toDateInputValue(now),
  };
}

function buildPaymentReportFilters(period: ReportPeriodDraft): AdminPaymentReportFilters {
  if (period.preset === "all") {
    return {};
  }
  return {
    date_from: period.dateFrom ? startOfLocalDayIso(period.dateFrom) : undefined,
    date_to: period.dateTo ? endOfLocalDayIso(period.dateTo) : undefined,
  };
}

function formatMinorAmount(amountMinor: number, currency: string, language: string) {
  try {
    return new Intl.NumberFormat(getIntlLocale(language), {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amountMinor / 100);
  } catch {
    return `${(amountMinor / 100).toFixed(2)} ${currency}`;
  }
}

function formatPercent(value: number, language: string) {
  return new Intl.NumberFormat(getIntlLocale(language), {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatOptionalDate(value: string | null | undefined, fallback: string, language: string) {
  return value ? formatDateTime(value, language) : fallback;
}

function statusTone(status: string): "success" | "error" | "warning" | "info" | "neutral" {
  if (["succeeded", "completed", "processed", "refunded"].includes(status)) {
    return "success";
  }
  if (["failed", "cancelled", "expired", "skipped"].includes(status)) {
    return "error";
  }
  if (["requires_action", "pending", "processing", "partially_refunded"].includes(status)) {
    return "warning";
  }
  return "neutral";
}

function StatusChip({ status }: { status: string }) {
  return <span className={`admin-payment-chip admin-payment-chip--${statusTone(status)}`}>{formatStateLabel(status)}</span>;
}

function SnapshotBlock({
  snapshot,
  emptyLabel,
}: {
  snapshot: Record<string, unknown> | null | undefined;
  emptyLabel: string;
}) {
  if (!snapshot || Object.keys(snapshot).length === 0) {
    return <p className="muted">{emptyLabel}</p>;
  }

  const text = JSON.stringify(snapshot, null, 2);
  return (
    <pre className="admin-payments-snapshot">
      {text.length > 1200 ? `${text.slice(0, 1200)}...` : text}
    </pre>
  );
}

export function AdminPaymentsPage() {
  const { paymentId } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [reportPeriod, setReportPeriod] = useState<ReportPeriodDraft>(() => createReportPeriod("30d"));
  const [report, setReport] = useState<PaymentReport | null>(null);
  const [filters, setFilters] = useState<FilterDraft>(DEFAULT_FILTERS);
  const [draftFilters, setDraftFilters] = useState<FilterDraft>(DEFAULT_FILTERS);
  const [payments, setPayments] = useState<AdminPaymentListItem[]>([]);
  const [details, setDetails] = useState<AdminPaymentDetails | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailsLoading, setIsDetailsLoading] = useState(false);
  const [isRefunding, setIsRefunding] = useState(false);
  const [reportErrorMessage, setReportErrorMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [detailsErrorMessage, setDetailsErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [refundMode, setRefundMode] = useState<"full" | "partial">("full");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundReason, setRefundReason] = useState("admin_adjustment");

  const selectedPayment = useMemo(
    () => payments.find((payment) => payment.id === paymentId) ?? null,
    [paymentId, payments],
  );

  const loadPaymentReport = useCallback(async () => {
    setIsReportLoading(true);
    setReportErrorMessage("");
    try {
      const response = await getAdminPaymentReportRequest(buildPaymentReportFilters(reportPeriod));
      setReport(response.data);
    } catch (error) {
      setReport(null);
      setReportErrorMessage(extractApiErrorMessage(error, t("admin.payments.analytics.states.unavailable")));
    } finally {
      setIsReportLoading(false);
    }
  }, [reportPeriod, t]);

  const loadPayments = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");
    try {
      const response = await listAdminPaymentsRequest(buildAdminPaymentFilters(filters));
      setPayments(response.data);
      if (!paymentId && response.data.length > 0) {
        navigate(`/admin/payments/${response.data[0].id}`, { replace: true });
      }
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("admin.payments.states.unavailable")));
      setPayments([]);
    } finally {
      setIsLoading(false);
    }
  }, [filters, navigate, paymentId, t]);

  const loadPaymentDetails = useCallback(async () => {
    if (!paymentId) {
      setDetails(null);
      setDetailsErrorMessage("");
      return;
    }

    setIsDetailsLoading(true);
    setDetailsErrorMessage("");
    try {
      const response = await getAdminPaymentDetailsRequest(paymentId);
      setDetails(response.data);
      setRefundMode("full");
      setRefundAmount("");
      setRefundReason("admin_adjustment");
    } catch (error) {
      setDetails(null);
      setDetailsErrorMessage(extractApiErrorMessage(error, t("admin.payments.states.detailsUnavailable")));
    } finally {
      setIsDetailsLoading(false);
    }
  }, [paymentId, t]);

  useEffect(() => {
    void loadPaymentReport();
  }, [loadPaymentReport]);

  useEffect(() => {
    void loadPayments();
  }, [loadPayments]);

  useEffect(() => {
    void loadPaymentDetails();
  }, [loadPaymentDetails]);

  function handleFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters(draftFilters);
  }

  function handleClearFilters() {
    setDraftFilters(DEFAULT_FILTERS);
    setFilters(DEFAULT_FILTERS);
  }

  function handleReportPresetChange(preset: ReportPreset) {
    setReportPeriod(createReportPeriod(preset));
  }

  function handleReportDateChange(field: "dateFrom" | "dateTo", value: string) {
    setReportPeriod((current) => ({ ...current, preset: "custom", [field]: value }));
  }

  async function handleRefundSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!details || !details.refundable) {
      setFeedback({
        tone: "warning",
        title: t("admin.payments.states.refundNotAllowedTitle"),
        message: t("admin.payments.states.refundNotAllowedMessage"),
      });
      return;
    }

    const payloadAmount =
      refundMode === "partial" ? Math.round(Number(refundAmount.replace(",", ".")) * 100) : undefined;
    if (refundMode === "partial" && (!payloadAmount || payloadAmount <= 0)) {
      setFeedback({
        tone: "error",
        title: t("admin.payments.states.refundFailureTitle"),
        message: t("admin.payments.states.invalidRefundAmount"),
      });
      return;
    }

    setIsRefunding(true);
    setFeedback(null);
    try {
      await createAdminPaymentRefundRequest(details.id, {
        amount_minor: payloadAmount,
        reason: refundReason,
        metadata: { source: "admin_payment_workspace" },
      });
      setFeedback({
        tone: "success",
        title: t("admin.payments.states.refundSuccessTitle"),
        message: t("admin.payments.states.refundSuccessMessage"),
      });
      await Promise.all([loadPaymentReport(), loadPayments(), loadPaymentDetails()]);
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("admin.payments.states.refundFailureTitle"),
        message: extractApiErrorMessage(error, t("admin.payments.states.refundFailureMessage")),
      });
    } finally {
      setIsRefunding(false);
    }
  }

  function renderPaymentAnalytics() {
    const generatedLabel = report
      ? t("admin.payments.analytics.generated", {
          date: formatDateTime(report.generated_at, i18n.language),
        })
      : "";

    return (
      <section className="panel admin-payment-analytics">
        <div className="admin-payment-analytics__header">
          <div>
            <p className="page-eyebrow">{t("admin.payments.analytics.eyebrow")}</p>
            <h2 className="section-title">{t("admin.payments.analytics.title")}</h2>
            <p className="muted">{t("admin.payments.analytics.intro")}</p>
          </div>
          <button className="button--ghost" type="button" onClick={() => void loadPaymentReport()} disabled={isReportLoading}>
            {t("admin.payments.analytics.actions.refresh")}
          </button>
        </div>

        <div className="admin-payment-report-controls">
          <div className="admin-payment-report-presets" role="group" aria-label={t("admin.payments.analytics.period.label")}>
            {REPORT_PRESETS.map((preset) => (
              <button
                className={reportPeriod.preset === preset ? "is-active" : undefined}
                key={preset}
                type="button"
                onClick={() => handleReportPresetChange(preset)}
              >
                {t(`admin.payments.analytics.period.${preset}`)}
              </button>
            ))}
          </div>
          <label className="field">
            <span>{t("admin.payments.analytics.period.from")}</span>
            <input
              type="date"
              value={reportPeriod.dateFrom}
              onChange={(event) => handleReportDateChange("dateFrom", event.target.value)}
            />
          </label>
          <label className="field">
            <span>{t("admin.payments.analytics.period.to")}</span>
            <input
              type="date"
              value={reportPeriod.dateTo}
              onChange={(event) => handleReportDateChange("dateTo", event.target.value)}
            />
          </label>
        </div>

        {isReportLoading ? (
          <StatePanel
            tone="loading"
            title={t("admin.payments.analytics.states.loadingTitle")}
            message={t("admin.payments.analytics.states.loadingMessage")}
          />
        ) : reportErrorMessage ? (
          <StatePanel
            tone="error"
            title={t("admin.payments.analytics.states.errorTitle")}
            message={reportErrorMessage}
            action={
              <button className="button--ghost" type="button" onClick={() => void loadPaymentReport()}>
                {t("common.actions.retry")}
              </button>
            }
          />
        ) : report ? (
          <div className="admin-payment-report">
            <div className="admin-payment-report-summary">
              <article className="admin-payment-report-card admin-payment-report-card--feature">
                <span>{t("admin.payments.analytics.summary.grossRevenue")}</span>
                <strong>
                  {formatMinorAmount(report.summary.gross_revenue_minor, report.summary.currency, i18n.language)}
                </strong>
                <p>{t("admin.payments.analytics.summary.grossRevenueDetail")}</p>
              </article>
              <article className="admin-payment-report-card admin-payment-report-card--feature">
                <span>{t("admin.payments.analytics.summary.netRevenue")}</span>
                <strong>
                  {formatMinorAmount(report.summary.net_revenue_minor, report.summary.currency, i18n.language)}
                </strong>
                <p>{t("admin.payments.analytics.summary.netRevenueDetail")}</p>
              </article>
              <article className="admin-payment-report-card">
                <span>{t("admin.payments.analytics.summary.refunded")}</span>
                <strong>
                  {formatMinorAmount(report.summary.refunded_amount_minor, report.summary.currency, i18n.language)}
                </strong>
                <p>{t("admin.payments.analytics.summary.refundedDetail")}</p>
              </article>
              <article className="admin-payment-report-card">
                <span>{t("admin.payments.analytics.summary.succeeded")}</span>
                <strong>{report.summary.succeeded_payments_count}</strong>
                <p>{t("admin.payments.analytics.summary.succeededDetail")}</p>
              </article>
              <article className="admin-payment-report-card">
                <span>{t("admin.payments.analytics.summary.failed")}</span>
                <strong>{report.summary.failed_payments_count}</strong>
                <p>{t("admin.payments.analytics.summary.failedDetail")}</p>
              </article>
              <article className="admin-payment-report-card">
                <span>{t("admin.payments.analytics.summary.pending")}</span>
                <strong>{report.summary.pending_payments_count}</strong>
                <p>{t("admin.payments.analytics.summary.pendingDetail")}</p>
              </article>
              <article className="admin-payment-report-card">
                <span>{t("admin.payments.analytics.summary.tickets")}</span>
                <strong>{report.summary.paid_tickets_count}</strong>
                <p>{t("admin.payments.analytics.summary.ticketsDetail")}</p>
              </article>
              <article className="admin-payment-report-card">
                <span>{t("admin.payments.analytics.summary.successRate")}</span>
                <strong>{formatPercent(report.summary.success_rate, i18n.language)}</strong>
                <p>{t("admin.payments.analytics.summary.successRateDetail")}</p>
              </article>
            </div>

            <p className="muted admin-payment-report__generated">{generatedLabel}</p>

            <div className="admin-payment-report-grids">
              <PaymentReportSessionTable
                rows={report.sessions}
                title={t("admin.payments.analytics.sessions.title")}
                empty={t("admin.payments.analytics.sessions.empty")}
                language={i18n.language}
              />
              <PaymentReportMovieTable
                rows={report.movies}
                title={t("admin.payments.analytics.movies.title")}
                empty={t("admin.payments.analytics.movies.empty")}
                language={i18n.language}
              />
            </div>
          </div>
        ) : null}
      </section>
    );
  }

  function renderPaymentList() {
    if (isLoading) {
      return (
        <StatePanel
          tone="loading"
          title={t("admin.payments.states.loadingTitle")}
          message={t("admin.payments.states.loadingMessage")}
        />
      );
    }

    if (errorMessage) {
      return (
        <StatePanel
          tone="error"
          title={t("admin.payments.states.errorTitle")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadPayments()}>
              {t("common.actions.retry")}
            </button>
          }
        />
      );
    }

    if (payments.length === 0) {
      return (
        <StatePanel
          title={t("admin.payments.states.emptyTitle")}
          message={t("admin.payments.states.emptyMessage")}
        />
      );
    }

    return (
      <div className="admin-payments-table-wrap">
        <table className="admin-payments-table">
          <thead>
            <tr>
              <th>{t("admin.payments.labels.payment")}</th>
              <th>{t("admin.payments.labels.order")}</th>
              <th>{t("admin.payments.labels.customer")}</th>
              <th>{t("admin.payments.labels.amount")}</th>
              <th>{t("admin.payments.labels.refundable")}</th>
              <th>{t("admin.payments.labels.updated")}</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((payment) => (
              <tr key={payment.id} className={payment.id === paymentId ? "is-selected" : undefined}>
                <td>
                  <Link className="admin-payments-table__identity" to={`/admin/payments/${payment.id}`}>
                    <strong>{payment.id}</strong>
                    <span>{payment.provider_payment_id ?? t("admin.payments.labels.noProviderRef")}</span>
                    <StatusChip status={payment.status} />
                  </Link>
                </td>
                <td>
                  <span>{payment.order_id}</span>
                  {payment.order_status ? <StatusChip status={payment.order_status} /> : null}
                </td>
                <td>
                  <strong>{payment.customer_name ?? payment.user_id}</strong>
                  <span>{payment.customer_email ?? payment.user_id}</span>
                </td>
                <td>{formatMinorAmount(payment.amount_minor, payment.currency, i18n.language)}</td>
                <td>
                  <strong>
                    {formatMinorAmount(
                      payment.remaining_refundable_amount_minor,
                      payment.currency,
                      i18n.language,
                    )}
                  </strong>
                  <span>{t("admin.payments.labels.refundsCount", { count: payment.refunds_count })}</span>
                </td>
                <td>{formatOptionalDate(payment.updated_at ?? payment.created_at, "-", i18n.language)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  function renderDetails() {
    if (!paymentId) {
      return (
        <StatePanel
          title={t("admin.payments.states.noDetailsTitle")}
          message={t("admin.payments.states.noDetailsMessage")}
        />
      );
    }

    if (isDetailsLoading) {
      return (
        <StatePanel
          tone="loading"
          title={t("admin.payments.states.detailsLoadingTitle")}
          message={t("admin.payments.states.detailsLoadingMessage")}
        />
      );
    }

    if (detailsErrorMessage) {
      return (
        <StatePanel
          tone="error"
          title={t("admin.payments.states.detailsErrorTitle")}
          message={detailsErrorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void loadPaymentDetails()}>
              {t("common.actions.retry")}
            </button>
          }
        />
      );
    }

    if (!details) {
      return null;
    }

    const movieTitle = getLocalizedText(details.order?.movie_title, i18n.language);
    const remainingRefundable = formatMinorAmount(
      details.remaining_refundable_amount_minor,
      details.currency,
      i18n.language,
    );

    return (
      <div className="admin-payment-details">
        <section className="panel admin-payment-details__summary">
          <div className="admin-payment-details__heading">
            <div>
              <p className="page-eyebrow">{t("admin.payments.labels.selectedPayment")}</p>
              <h2 className="section-title">{details.id}</h2>
              <p className="muted">{details.provider_payment_id ?? t("admin.payments.labels.noProviderRef")}</p>
            </div>
            <StatusChip status={details.status} />
          </div>

          <div className="admin-payment-facts">
            <div>
              <span>{t("admin.payments.labels.amount")}</span>
              <strong>{formatMinorAmount(details.amount_minor, details.currency, i18n.language)}</strong>
            </div>
            <div>
              <span>{t("admin.payments.labels.refunded")}</span>
              <strong>{formatMinorAmount(details.refunded_amount_minor, details.currency, i18n.language)}</strong>
            </div>
            <div>
              <span>{t("admin.payments.labels.remaining")}</span>
              <strong>{remainingRefundable}</strong>
            </div>
            <div>
              <span>{t("admin.payments.labels.provider")}</span>
              <strong>{details.provider}</strong>
            </div>
          </div>

          {details.failure_code || details.failure_message ? (
            <StatusBanner
              tone="error"
              title={details.failure_code ?? t("admin.payments.labels.failure")}
              message={details.failure_message ?? t("admin.payments.labels.failure")}
            />
          ) : null}
        </section>

        <section className="panel admin-payment-section">
          <div className="admin-payment-section__header">
            <div>
              <h3>{t("admin.payments.labels.bookingContext")}</h3>
              <p className="muted">
                {movieTitle || details.order?.session_id || t("admin.payments.states.bookingUnavailable")}
              </p>
            </div>
            {details.order?.order_status ? <StatusChip status={details.order.order_status} /> : null}
          </div>
          <div className="admin-payment-facts admin-payment-facts--compact">
            <div>
              <span>{t("admin.payments.labels.order")}</span>
              <strong>{details.order?.order_id ?? details.order_id}</strong>
            </div>
            <div>
              <span>{t("admin.payments.labels.session")}</span>
              <strong>{details.order?.session_id ?? "-"}</strong>
              <p>{formatOptionalDate(details.order?.session_start_time, "-", i18n.language)}</p>
            </div>
            <div>
              <span>{t("admin.payments.labels.seats")}</span>
              <strong>{details.order?.seats.join(", ") || "-"}</strong>
            </div>
            <div>
              <span>{t("admin.payments.labels.customer")}</span>
              <strong>{details.customer?.name ?? details.user_id}</strong>
              <p>{details.customer?.email ?? details.user_id}</p>
            </div>
          </div>
        </section>

        <section className="panel admin-payment-section">
          <div className="admin-payment-section__header">
            <div>
              <h3>{t("admin.payments.labels.refundActions")}</h3>
              <p className="muted">
                {details.refundable
                  ? t("admin.payments.states.refundAllowed", { amount: remainingRefundable })
                  : t("admin.payments.states.refundNotAllowedMessage")}
              </p>
            </div>
          </div>
          <form className="admin-refund-form" onSubmit={(event) => void handleRefundSubmit(event)}>
            <label className="field">
              <span>{t("admin.payments.labels.refundMode")}</span>
              <select value={refundMode} onChange={(event) => setRefundMode(event.target.value as "full" | "partial")}>
                <option value="full">{t("admin.payments.labels.fullRefund")}</option>
                <option value="partial">{t("admin.payments.labels.partialRefund")}</option>
              </select>
            </label>
            {refundMode === "partial" ? (
              <label className="field">
                <span>{t("admin.payments.labels.refundAmount")}</span>
                <input
                  min="0"
                  step="0.01"
                  type="number"
                  value={refundAmount}
                  onChange={(event) => setRefundAmount(event.target.value)}
                  placeholder="100.00"
                />
              </label>
            ) : null}
            <label className="field">
              <span>{t("admin.payments.labels.reason")}</span>
              <input value={refundReason} onChange={(event) => setRefundReason(event.target.value)} />
            </label>
            <button className="button" type="submit" disabled={!details.refundable || isRefunding}>
              {isRefunding ? t("admin.payments.actions.refunding") : t("admin.payments.actions.issueRefund")}
            </button>
          </form>
        </section>

        <HistorySection title={t("admin.payments.labels.attemptHistory")} empty={t("admin.payments.states.noAttempts")}>
          {details.attempts.map((attempt) => (
            <article className="admin-payment-history-card" key={attempt.id}>
              <div className="admin-payment-history-card__header">
                <strong>{attempt.id}</strong>
                <StatusChip status={attempt.status} />
              </div>
              <p className="muted">{attempt.provider_attempt_id ?? t("admin.payments.labels.noProviderRef")}</p>
              {attempt.error_code || attempt.error_message ? (
                <p className="admin-payment-history-card__error">
                  {attempt.error_code} {attempt.error_message}
                </p>
              ) : null}
              <SnapshotBlock snapshot={attempt.response_payload_snapshot} emptyLabel={t("admin.payments.states.noSnapshot")} />
            </article>
          ))}
        </HistorySection>

        <HistorySection title={t("admin.payments.labels.refundHistory")} empty={t("admin.payments.states.noRefunds")}>
          {details.refunds.map((refund) => (
            <article className="admin-payment-history-card" key={refund.id}>
              <div className="admin-payment-history-card__header">
                <strong>{formatMinorAmount(refund.amount_minor, refund.currency, i18n.language)}</strong>
                <StatusChip status={refund.status} />
              </div>
              <p className="muted">{refund.reason}</p>
              <p>{refund.provider_refund_id ?? t("admin.payments.labels.noProviderRef")}</p>
              {refund.failure_code || refund.failure_message ? (
                <p className="admin-payment-history-card__error">
                  {refund.failure_code} {refund.failure_message}
                </p>
              ) : null}
            </article>
          ))}
        </HistorySection>

        <HistorySection title={t("admin.payments.labels.webhookHistory")} empty={t("admin.payments.states.noWebhooks")}>
          {details.webhook_events.map((event) => (
            <article className="admin-payment-history-card" key={event.id}>
              <div className="admin-payment-history-card__header">
                <strong>{event.event_type}</strong>
                <StatusChip status={event.processing_status} />
              </div>
              <p className="muted">{event.provider_event_id ?? event.id}</p>
              <div className="admin-payment-history-card__meta">
                <span>
                  {t("admin.payments.labels.signature")}:{" "}
                  {event.signature_verified ? t("checkout.labels.yes") : t("checkout.labels.no")}
                </span>
                <span>
                  {t("admin.payments.labels.processedAt")}:{" "}
                  {formatOptionalDate(event.processed_at, "-", i18n.language)}
                </span>
              </div>
              {event.error_message ? <p className="admin-payment-history-card__error">{event.error_message}</p> : null}
              <SnapshotBlock snapshot={event.payload_snapshot} emptyLabel={t("admin.payments.states.noSnapshot")} />
            </article>
          ))}
        </HistorySection>
      </div>
    );
  }

  return (
    <>
      <section className="page-header admin-payments-header">
        <div>
          <p className="page-eyebrow">{t("admin.payments.page.eyebrow")}</p>
          <h1 className="page-title">{t("admin.payments.page.title")}</h1>
          <p className="page-subtitle">{t("admin.payments.page.intro")}</p>
        </div>
        <div className="actions-row">
          <Link className="button--ghost" to="/admin">
            {t("common.actions.backToAdmin")}
          </Link>
          <button
            className="button--ghost"
            type="button"
            onClick={() => void Promise.all([loadPaymentReport(), loadPayments(), loadPaymentDetails()])}
            disabled={isLoading || isReportLoading || isDetailsLoading}
          >
            {t("admin.payments.actions.refresh")}
          </button>
        </div>
      </section>

      {feedback ? <StatusBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}

      {renderPaymentAnalytics()}

      <section className="panel admin-payments-filters">
        <form onSubmit={handleFilterSubmit}>
          <label className="field">
            <span>{t("admin.payments.filters.search")}</span>
            <input
              value={draftFilters.search}
              onChange={(event) => setDraftFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder={t("admin.payments.filters.searchPlaceholder")}
            />
          </label>
          <label className="field">
            <span>{t("admin.payments.filters.status")}</span>
            <select
              value={draftFilters.status}
              onChange={(event) => setDraftFilters((current) => ({ ...current, status: event.target.value }))}
            >
              <option value="">{t("admin.payments.filters.allStatuses")}</option>
              {PAYMENT_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {formatStateLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("admin.payments.filters.provider")}</span>
            <input
              value={draftFilters.provider}
              onChange={(event) => setDraftFilters((current) => ({ ...current, provider: event.target.value }))}
              placeholder="fake"
            />
          </label>
          <label className="field">
            <span>{t("admin.payments.filters.refundStatus")}</span>
            <select
              value={draftFilters.refundStatus}
              onChange={(event) => setDraftFilters((current) => ({ ...current, refundStatus: event.target.value }))}
            >
              <option value="">{t("admin.payments.filters.allRefunds")}</option>
              <option value="none">{t("admin.payments.filters.noRefunds")}</option>
              {REFUND_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {formatStateLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <div className="actions-row">
            <button className="button" type="submit">
              {t("admin.payments.actions.applyFilters")}
            </button>
            <button className="button--ghost" type="button" onClick={handleClearFilters}>
              {t("admin.payments.actions.clearFilters")}
            </button>
          </div>
        </form>
      </section>

      <section className="admin-payments-workspace">
        <div className="admin-payments-list">
          <div className="admin-payments-list__header">
            <div>
              <p className="page-eyebrow">{t("admin.payments.labels.paymentsList")}</p>
              <h2 className="section-title">{t("admin.payments.labels.paymentsCount", { count: payments.length })}</h2>
            </div>
            {selectedPayment ? <StatusChip status={selectedPayment.status} /> : null}
          </div>
          {renderPaymentList()}
        </div>
        {renderDetails()}
      </section>
    </>
  );
}

function PaymentReportSessionTable({
  rows,
  title,
  empty,
  language,
}: {
  rows: PaymentReportSessionAggregate[];
  title: string;
  empty: string;
  language: string;
}) {
  const { t } = useTranslation();
  return (
    <section className="admin-payment-report-table-card">
      <div className="admin-payment-report-table-card__header">
        <h3>{title}</h3>
        <span className="badge">{t("admin.payments.analytics.resultCount", { count: rows.length })}</span>
      </div>
      {rows.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <div className="admin-payment-report-table-wrap">
          <table className="admin-payment-report-table">
            <thead>
              <tr>
                <th>{t("admin.payments.analytics.table.session")}</th>
                <th>{t("admin.payments.analytics.table.gross")}</th>
                <th>{t("admin.payments.analytics.table.refunded")}</th>
                <th>{t("admin.payments.analytics.table.net")}</th>
                <th>{t("admin.payments.analytics.table.volume")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const movieTitle = getLocalizedText(row.movie_title, language) || row.movie_id || row.session_id;
                return (
                  <tr key={row.session_id}>
                    <td>
                      <strong>{movieTitle}</strong>
                      <span>{formatOptionalDate(row.session_start_time, row.session_id, language)}</span>
                    </td>
                    <td>{formatMinorAmount(row.gross_revenue_minor, row.currency, language)}</td>
                    <td>{formatMinorAmount(row.refunded_amount_minor, row.currency, language)}</td>
                    <td>{formatMinorAmount(row.net_revenue_minor, row.currency, language)}</td>
                    <td>
                      <strong>{t("admin.payments.analytics.table.tickets", { count: row.paid_tickets_count })}</strong>
                      <span>{t("admin.payments.analytics.table.orders", { count: row.succeeded_orders_count })}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function PaymentReportMovieTable({
  rows,
  title,
  empty,
  language,
}: {
  rows: PaymentReportMovieAggregate[];
  title: string;
  empty: string;
  language: string;
}) {
  const { t } = useTranslation();
  return (
    <section className="admin-payment-report-table-card">
      <div className="admin-payment-report-table-card__header">
        <h3>{title}</h3>
        <span className="badge">{t("admin.payments.analytics.resultCount", { count: rows.length })}</span>
      </div>
      {rows.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <div className="admin-payment-report-table-wrap">
          <table className="admin-payment-report-table">
            <thead>
              <tr>
                <th>{t("admin.payments.analytics.table.movie")}</th>
                <th>{t("admin.payments.analytics.table.gross")}</th>
                <th>{t("admin.payments.analytics.table.refunded")}</th>
                <th>{t("admin.payments.analytics.table.net")}</th>
                <th>{t("admin.payments.analytics.table.volume")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const movieTitle = getLocalizedText(row.movie_title, language) || row.movie_id;
                return (
                  <tr key={row.movie_id}>
                    <td>
                      <strong>{movieTitle}</strong>
                      <span>{t("admin.payments.analytics.table.sessions", { count: row.paid_sessions_count })}</span>
                    </td>
                    <td>{formatMinorAmount(row.gross_revenue_minor, row.currency, language)}</td>
                    <td>{formatMinorAmount(row.refunded_amount_minor, row.currency, language)}</td>
                    <td>{formatMinorAmount(row.net_revenue_minor, row.currency, language)}</td>
                    <td>
                      <strong>{t("admin.payments.analytics.table.tickets", { count: row.paid_tickets_count })}</strong>
                      <span>{t("admin.payments.analytics.table.orders", { count: row.succeeded_orders_count })}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function HistorySection({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: ReactNode;
}) {
  const hasChildren = Children.count(children) > 0;
  return (
    <section className="panel admin-payment-section">
      <div className="admin-payment-section__header">
        <h3>{title}</h3>
      </div>
      {hasChildren ? <div className="admin-payment-history-list">{children}</div> : <p className="muted">{empty}</p>}
    </section>
  );
}
