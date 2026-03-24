import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
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
      setStatusMessage(t("registrationSuccess"));
      navigate("/login");
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("registrationFailed")));
    }
  }

  return (
    <form className="form-card" onSubmit={handleSubmit}>
      <h1>{t("createAccount")}</h1>
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
      <button className="button" type="submit">
        {t("register")}
      </button>
    </form>
  );
}
