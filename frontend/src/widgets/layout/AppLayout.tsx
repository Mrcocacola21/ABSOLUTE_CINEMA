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
              <span className="brand__title">{t("common.brand.title")}</span>
              <span className="brand__subtitle">{t("common.brand.tagline")}</span>
            </NavLink>
            <nav className="nav nav--primary" aria-label={t("common.navigation.primary")}>
              <NavLink to="/" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} end>
                {t("common.navigation.home")}
              </NavLink>
              <NavLink
                to="/movies"
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {t("common.navigation.movies")}
              </NavLink>
              <NavLink
                to="/schedule"
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {t("common.navigation.schedule")}
              </NavLink>
            </nav>
          </div>

          <div className="topbar__controls">
            <div className="lang-switcher" aria-label={t("common.language")}>
              <button
                type="button"
                className={activeLanguage === "uk" ? "is-active" : ""}
                onClick={() => handleLanguageChange("uk")}
              >
                UA
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
                    {t("common.navigation.login")}
                  </NavLink>
                  <NavLink
                    to="/register"
                    className={({ isActive }) => `nav-link nav-link--primary${isActive ? " active" : ""}`}
                  >
                    {t("common.navigation.register")}
                  </NavLink>
                </>
              ) : null}
              {isAuthLoading ? (
                <span className="user-pill">
                  <strong>{t("common.account.label")}</strong>
                  <span>{t("common.account.checkingSession")}</span>
                </span>
              ) : (
                currentUser ? (
                  <>
                  <NavLink
                    to="/profile"
                    className={({ isActive }) => `user-pill user-pill--link${isActive ? " active" : ""}`}
                  >
                    <strong>{currentUser.name}</strong>
                    <span>{t("common.navigation.profile")}</span>
                  </NavLink>
                  {role === "admin" ? (
                    <NavLink
                      to="/admin"
                      className={({ isActive }) => `nav-link nav-link--primary${isActive ? " active" : ""}`}
                    >
                      {t("common.navigation.admin")}
                    </NavLink>
                  ) : null}
                  <button type="button" className="nav-link nav-link--ghost" onClick={handleLogout}>
                    {t("common.navigation.logout")}
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
        {t("common.brand.title")}. {t("common.brand.tagline")}
      </footer>
    </div>
  );
}
