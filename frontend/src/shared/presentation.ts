import i18n from "@/i18n";
import { getIntlLocale } from "@/shared/localization";

function getLocale(language?: string): string {
  return getIntlLocale(language ?? i18n.resolvedLanguage ?? i18n.language);
}

export function formatCurrency(value: number, language?: string): string {
  return new Intl.NumberFormat(getLocale(language), {
    style: "currency",
    currency: "UAH",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatDateTime(value: string, language?: string): string {
  return new Date(value).toLocaleString(getLocale(language), {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTime(value: string, language?: string): string {
  return new Date(value).toLocaleTimeString(getLocale(language), {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function humanizeState(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

const stateTranslationKeyMap: Record<string, string> = {
  scheduled: "common.states.scheduled",
  cancelled: "common.states.cancelled",
  completed: "common.states.completed",
  purchased: "common.states.purchased",
  active: "common.states.active",
  planned: "common.states.planned",
  deactivated: "common.states.deactivated",
  inactive: "common.states.inactive",
  admin: "common.states.admin",
  user: "common.states.user",
  partially_cancelled: "common.states.partiallyCancelled",
};

export function formatStateLabel(value: string): string {
  const key = stateTranslationKeyMap[value];
  if (!key) {
    return humanizeState(value);
  }

  return i18n.t(key, { defaultValue: humanizeState(value) });
}
