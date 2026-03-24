import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { resources } from "@/i18n/resources";
import { STORAGE_KEYS } from "@/shared/constants";

const initialLanguage =
  typeof window !== "undefined"
    ? window.localStorage.getItem(STORAGE_KEYS.language) ?? "uk"
    : "uk";

void i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage,
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
