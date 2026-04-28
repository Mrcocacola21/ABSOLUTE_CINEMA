import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { StatusBanner } from "@/shared/ui/StatusBanner";

export function LoginPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState(
    typeof location.state === "object" &&
      location.state &&
      "statusMessage" in location.state &&
      typeof location.state.statusMessage === "string"
      ? location.state.statusMessage
      : "",
  );
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatusMessage("");
    setErrorMessage("");
    setIsSubmitting(true);
    try {
      await login(email.trim(), password);
      const redirectPath =
        typeof location.state === "object" &&
        location.state &&
        "from" in location.state &&
        typeof location.state.from === "string" &&
        location.state.from.startsWith("/")
          ? location.state.from
          : "/profile";
      navigate(redirectPath);
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("auth.login.failed")));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-shell">
      <section className="panel auth-aside">
        <p className="page-eyebrow">{t("auth.login.eyebrow")}</p>
        <h1 className="page-title auth-title">{t("auth.login.title")}</h1>
        <p className="page-subtitle">{t("auth.login.intro")}</p>
        <div className="actions-row">
          <Link to="/register" className="button--ghost">
            {t("common.actions.createAccount")}
          </Link>
        </div>
      </section>

      <form className="form-card auth-form" onSubmit={handleSubmit}>
        <h2 className="section-title">{t("auth.login.title")}</h2>
        <div className="form-grid">
          <label className="field">
            <span>{t("common.labels.email")}</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              disabled={isSubmitting}
              required
              autoComplete="email"
            />
          </label>
          <label className="field">
            <span>{t("common.labels.password")}</span>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              disabled={isSubmitting}
              required
              autoComplete="current-password"
            />
          </label>
        </div>
        {statusMessage ? <StatusBanner tone="info" message={statusMessage} /> : null}
        {errorMessage ? <StatusBanner tone="error" title={t("auth.login.errorTitle")} message={errorMessage} /> : null}
        <div className="actions-row">
          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("auth.login.submitting") : t("common.navigation.login")}
          </button>
          <Link to="/register" className="button--ghost">
            {t("auth.prompts.needAccount")}
          </Link>
        </div>
      </form>
    </section>
  );
}
