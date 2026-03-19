import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/features/auth/useAuth";

export function HomePage() {
  const { t } = useTranslation();
  const { role } = useAuth();

  return (
    <section className="hero">
      <p className="badge">One Hall Cinema</p>
      <h1>{t("welcomeTitle")}</h1>
      <p>{t("welcomeText")}</p>
      <div className="hero__actions">
        <Link to="/schedule" className="button">
          {t("browseSchedule")}
        </Link>
        <Link to={role === "admin" ? "/admin" : "/login"} className="button--ghost">
          {t("openAdmin")}
        </Link>
      </div>
    </section>
  );
}
