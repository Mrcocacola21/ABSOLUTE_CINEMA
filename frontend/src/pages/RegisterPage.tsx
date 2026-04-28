import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { registerRequest } from "@/api/auth";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { StatusBanner } from "@/shared/ui/StatusBanner";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatusMessage("");
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      await registerRequest({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      navigate("/login", {
        state: {
          statusMessage: t("auth.register.success"),
        },
      });
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("auth.register.failed")));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-shell">
      <section className="panel auth-aside">
        <p className="page-eyebrow">{t("auth.register.eyebrow")}</p>
        <h1 className="page-title auth-title">{t("auth.register.title")}</h1>
        <p className="page-subtitle">{t("auth.register.intro")}</p>
        <div className="actions-row">
          <Link to="/login" className="button--ghost">
            {t("common.actions.signIn")}
          </Link>
        </div>
      </section>

      <form className="form-card auth-form" onSubmit={handleSubmit}>
        <h2 className="section-title">{t("auth.register.title")}</h2>
        <div className="form-grid">
          <label className="field">
            <span>{t("common.labels.name")}</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={isSubmitting}
              required
              minLength={2}
              maxLength={255}
              pattern=".*\S.*"
              autoComplete="name"
            />
          </label>
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
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
            />
          </label>
        </div>
        {statusMessage ? <StatusBanner tone="info" message={statusMessage} /> : null}
        {errorMessage ? (
          <StatusBanner tone="error" title={t("auth.register.errorTitle")} message={errorMessage} />
        ) : null}
        <div className="actions-row">
          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("auth.register.submitting") : t("common.navigation.register")}
          </button>
          <Link to="/login" className="button--ghost">
            {t("auth.prompts.haveAccount")}
          </Link>
        </div>
      </form>
    </section>
  );
}
