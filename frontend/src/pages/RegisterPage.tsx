import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { registerRequest } from "@/api/auth";
import { extractApiErrorMessage } from "@/shared/apiErrors";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatusMessage("");
    setErrorMessage("");

    try {
      await registerRequest({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      navigate("/login", {
        state: {
          statusMessage: t("registrationSuccess"),
        },
      });
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("registrationFailed")));
    }
  }

  return (
    <section className="auth-shell">
      <section className="panel auth-aside">
        <p className="page-eyebrow">{t("register")}</p>
        <h1 className="page-title auth-title">{t("createAccount")}</h1>
        <p className="page-subtitle">{t("registerIntro")}</p>
        <div className="actions-row">
          <Link to="/login" className="button--ghost">
            {t("signIn")}
          </Link>
        </div>
      </section>

      <form className="form-card auth-form" onSubmit={handleSubmit}>
        <h2 className="section-title">{t("createAccount")}</h2>
        <div className="form-grid">
          <label className="field">
            <span>{t("name")}</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              minLength={2}
              maxLength={255}
            />
          </label>
          <label className="field">
            <span>{t("email")}</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              required
            />
          </label>
          <label className="field">
            <span>{t("password")}</span>
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              required
              minLength={8}
              maxLength={128}
            />
          </label>
        </div>
        {statusMessage ? <p className="badge">{statusMessage}</p> : null}
        {errorMessage ? <p className="badge badge--danger">{errorMessage}</p> : null}
        <div className="actions-row">
          <button className="button" type="submit">
            {t("register")}
          </button>
          <Link to="/login" className="button--ghost">
            {t("loginInstead")}
          </Link>
        </div>
      </form>
    </section>
  );
}
