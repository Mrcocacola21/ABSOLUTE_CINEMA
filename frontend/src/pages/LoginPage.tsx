import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { extractApiErrorMessage } from "@/shared/apiErrors";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await login(email, password);
      navigate("/profile");
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("loginFailed")));
    }
  }

  return (
    <form className="form-card" onSubmit={handleSubmit}>
      <h1>{t("signIn")}</h1>
      <div className="form-grid">
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
          />
        </label>
      </div>
      {errorMessage ? <p className="badge badge--danger">{errorMessage}</p> : null}
      <button className="button" type="submit">
        {t("login")}
      </button>
    </form>
  );
}
