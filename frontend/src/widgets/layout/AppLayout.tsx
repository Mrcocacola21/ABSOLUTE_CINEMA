import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/features/auth/useAuth";

export function AppLayout() {
  const { t, i18n } = useTranslation();
  const { currentUser, logout, role } = useAuth();

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__inner">
          <NavLink to="/" className="brand">
            {t("brand")}
          </NavLink>
          <nav className="nav">
            <NavLink to="/">{t("home")}</NavLink>
            <NavLink to="/schedule">{t("schedule")}</NavLink>
            {currentUser ? <NavLink to="/profile">{t("profile")}</NavLink> : null}
            {role === "admin" ? <NavLink to="/admin">{t("admin")}</NavLink> : null}
            {!currentUser ? <NavLink to="/login">{t("login")}</NavLink> : null}
            {!currentUser ? <NavLink to="/register">{t("register")}</NavLink> : null}
            {currentUser ? (
              <button type="button" onClick={logout}>
                {t("logout")}
              </button>
            ) : null}
          </nav>
          <div className="lang-switcher">
            <button type="button" onClick={() => void i18n.changeLanguage("uk")}>
              UK
            </button>
            <button type="button" onClick={() => void i18n.changeLanguage("en")}>
              EN
            </button>
          </div>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <footer className="footer">
        Cinema Showcase. One hall, four core entities, clean starter architecture.
      </footer>
    </div>
  );
}
