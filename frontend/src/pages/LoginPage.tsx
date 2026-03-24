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
      await login(email, password);
      navigate("/profile");
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("loginFailed")));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-shell">
      <section className="panel auth-aside">
        <p className="page-eyebrow">{t("login")}</p>
        <h1 className="page-title auth-title">{t("signIn")}</h1>
        <p className="page-subtitle">{t("loginIntro")}</p>
        <div className="actions-row">
          <Link to="/register" className="button--ghost">
            {t("createAccount")}
          </Link>
        </div>
      </section>

      <form className="form-card auth-form" onSubmit={handleSubmit}>
        <h2 className="section-title">{t("signIn")}</h2>
        <div className="form-grid">
          <label className="field">
            <span>{t("email")}</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              disabled={isSubmitting}
              required
            />
          </label>
          <label className="field">
            <span>{t("password")}</span>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              disabled={isSubmitting}
              required
            />
          </label>
        </div>
        {statusMessage ? <StatusBanner tone="info" message={statusMessage} /> : null}
        {errorMessage ? <StatusBanner tone="error" title="Unable to sign in" message={errorMessage} /> : null}
        <div className="actions-row">
          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : t("login")}
          </button>
          <Link to="/register" className="button--ghost">
            {t("registerInstead")}
          </Link>
        </div>
      </form>
    </section>
  );
}
