import { useTranslation } from "react-i18next";

import { useAuth } from "@/features/auth/useAuth";

export function ProfilePage() {
  const { t } = useTranslation();
  const { currentUser } = useAuth();

  return (
    <section className="panel">
      <h1 className="page-title">{t("profile")}</h1>
      {!currentUser ? <p className="muted">{t("profileLoading")}</p> : null}
      {currentUser ? (
        <div className="stats-row">
          <span className="badge">{currentUser.name}</span>
          <span className="badge">{currentUser.email}</span>
          <span className="badge">{currentUser.role}</span>
        </div>
      ) : null}
    </section>
  );
}
