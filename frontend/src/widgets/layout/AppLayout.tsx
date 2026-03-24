import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/features/auth/useAuth";
import { STORAGE_KEYS } from "@/shared/constants";

export function AppLayout() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { currentUser, isAuthLoading, logout, role } = useAuth();
  const activeLanguage = i18n.resolvedLanguage ?? i18n.language;

  function handleLanguageChange(language: "uk" | "en") {
    window.localStorage.setItem(STORAGE_KEYS.language, language);
    void i18n.changeLanguage(language);
  }

  function handleLogout() {
    logout();
    navigate("/", { replace: true });
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="topbar__left">
            <NavLink to="/" className="brand">
              <span className="brand__title">{t("brand")}</span>
              <span className="brand__subtitle">{t("brandTagline")}</span>
            </NavLink>
            <nav className="nav nav--primary" aria-label={t("primaryNavigation")}>
              <NavLink to="/" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} end>
                {t("home")}
              </NavLink>
              <NavLink
                to="/movies"
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {t("movies")}
              </NavLink>
              <NavLink
                to="/schedule"
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {t("schedule")}
              </NavLink>
            </nav>
          </div>

          <div className="topbar__controls">
            <div className="lang-switcher" aria-label={t("language")}>
              <button
                type="button"
                className={activeLanguage === "uk" ? "is-active" : ""}
                onClick={() => handleLanguageChange("uk")}
              >
                UK
              </button>
              <button
                type="button"
                className={activeLanguage === "en" ? "is-active" : ""}
                onClick={() => handleLanguageChange("en")}
              >
                EN
              </button>
            </div>

            <div className="nav nav--actions">
              {!currentUser && !isAuthLoading ? (
                <>
                  <NavLink
                    to="/login"
                    className={({ isActive }) => `nav-link nav-link--ghost${isActive ? " active" : ""}`}
                  >
                    {t("login")}
                  </NavLink>
                  <NavLink
                    to="/register"
                    className={({ isActive }) => `nav-link nav-link--primary${isActive ? " active" : ""}`}
                  >
                    {t("register")}
                  </NavLink>
                </>
              ) : null}
              {isAuthLoading ? (
                <span className="user-pill">
                  <strong>Account</strong>
                  <span>Checking session...</span>
                </span>
              ) : (
                currentUser ? (
                  <>
                  <span className="user-pill">
                    <strong>{currentUser.name}</strong>
                    <span>{role === "admin" ? t("admin") : t("profile")}</span>
                  </span>
                  <NavLink
                    to="/profile"
                    className={({ isActive }) => `nav-link nav-link--ghost${isActive ? " active" : ""}`}
                  >
                    {t("profile")}
                  </NavLink>
                  {role === "admin" ? (
                    <NavLink
                      to="/admin"
                      className={({ isActive }) => `nav-link nav-link--primary${isActive ? " active" : ""}`}
                    >
                      {t("admin")}
                    </NavLink>
                  ) : null}
                  <button type="button" className="nav-link nav-link--ghost" onClick={handleLogout}>
                    {t("logout")}
                  </button>
                  </>
                ) : null
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <footer className="footer">
        {t("footerNote")}
      </footer>
    </div>
  );
}
