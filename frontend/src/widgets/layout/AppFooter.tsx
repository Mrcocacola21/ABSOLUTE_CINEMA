import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "./AppFooter.css";

const EASTER_EGG_CLICK_TARGET = 5;
const EASTER_EGG_RESET_DELAY_MS = 1800;
const EASTER_EGG_GIF_SRC = "/gojo-absolute-cinema.gif";

export function AppFooter() {
  const { t } = useTranslation();
  const [isEasterEggOpen, setIsEasterEggOpen] = useState(false);
  const brandClickCountRef = useRef(0);
  const clickResetTimerRef = useRef<number | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  const clearClickResetTimer = useCallback(() => {
    if (clickResetTimerRef.current !== null) {
      window.clearTimeout(clickResetTimerRef.current);
      clickResetTimerRef.current = null;
    }
  }, []);

  const resetBrandClickCount = useCallback(() => {
    clearClickResetTimer();
    brandClickCountRef.current = 0;
  }, [clearClickResetTimer]);

  const handleBrandClick = useCallback(() => {
    clearClickResetTimer();
    brandClickCountRef.current += 1;

    if (brandClickCountRef.current >= EASTER_EGG_CLICK_TARGET) {
      resetBrandClickCount();
      setIsEasterEggOpen(true);
      return;
    }

    clickResetTimerRef.current = window.setTimeout(() => {
      resetBrandClickCount();
    }, EASTER_EGG_RESET_DELAY_MS);
  }, [clearClickResetTimer, resetBrandClickCount]);

  const dismissEasterEgg = useCallback(() => {
    resetBrandClickCount();
    setIsEasterEggOpen(false);
  }, [resetBrandClickCount]);

  useEffect(() => {
    return () => {
      clearClickResetTimer();
    };
  }, [clearClickResetTimer]);

  useEffect(() => {
    if (!isEasterEggOpen) {
      return;
    }

    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        dismissEasterEgg();
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [dismissEasterEgg, isEasterEggOpen]);

  return (
    <footer className="footer" aria-label="Site footer">
      <div className="footer__inner">
        <div className="footer__brand-block">
          <button type="button" className="footer__brand" onClick={handleBrandClick}>
            {t("common.brand.title")}
          </button>
          <p className="footer__tagline">{t("common.brand.tagline")}</p>
        </div>

        <nav className="footer__nav" aria-label={t("common.navigation.primary")}>
          <NavLink to="/" className={({ isActive }) => `footer__link${isActive ? " is-active" : ""}`} end>
            {t("common.navigation.home")}
          </NavLink>
          <NavLink to="/movies" className={({ isActive }) => `footer__link${isActive ? " is-active" : ""}`}>
            {t("common.navigation.movies")}
          </NavLink>
          <NavLink to="/schedule" className={({ isActive }) => `footer__link${isActive ? " is-active" : ""}`}>
            {t("common.navigation.schedule")}
          </NavLink>
        </nav>

        <p className="footer__meta">Course project / {new Date().getFullYear()}</p>
      </div>

      {isEasterEggOpen ? (
        <div className="easter-egg" onClick={dismissEasterEgg}>
          <div
            className="easter-egg__dialog"
            role="dialog"
            aria-modal="true"
            aria-label={`${t("common.brand.title")} easter egg`}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              ref={closeButtonRef}
              type="button"
              className="easter-egg__close"
              aria-label={t("common.actions.dismiss")}
              onClick={dismissEasterEgg}
            >
              X
            </button>
            <div className="easter-egg__screen">
              <img src={EASTER_EGG_GIF_SRC} alt="Gojo absolute cinema" />
            </div>
            <div className="easter-egg__caption">
              <span className="easter-egg__eyebrow">Absolute cinema</span>
              <strong>{t("common.brand.title")}</strong>
            </div>
          </div>
        </div>
      ) : null}
    </footer>
  );
}
