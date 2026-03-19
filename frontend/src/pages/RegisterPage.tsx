import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { registerRequest } from "@/api/auth";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await registerRequest({
        name,
        email,
        password,
      });
      setMessage(t("registrationSuccess"));
      navigate("/login");
    } catch {
      setMessage(t("registrationFailed"));
    }
  }

  return (
    <form className="form-card" onSubmit={handleSubmit}>
      <h1>{t("createAccount")}</h1>
      <div className="form-grid">
        <label className="field">
          <span>{t("name")}</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="field">
          <span>{t("email")}</span>
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
        </label>
        <label className="field">
          <span>{t("password")}</span>
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
          />
        </label>
      </div>
      {message ? <p className="badge">{message}</p> : null}
      <button className="button" type="submit">
        {t("register")}
      </button>
    </form>
  );
}
