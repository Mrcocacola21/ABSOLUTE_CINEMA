import type { LocalizedText } from "@/types/domain";

export type SupportedLanguageCode = "uk" | "en";

export function normalizeLanguageCode(language?: string): SupportedLanguageCode {
  return language?.toLowerCase().startsWith("en") ? "en" : "uk";
}

export function getIntlLocale(language?: string): string {
  return normalizeLanguageCode(language) === "en" ? "en-US" : "uk-UA";
}

export function getLocalizedText(text: LocalizedText | null | undefined, language: string): string {
  if (!text) {
    return "";
  }

  const normalizedLanguage = normalizeLanguageCode(language);
  const preferredValue = text[normalizedLanguage]?.trim() ?? "";
  const ukrainianValue = text.uk?.trim() ?? "";
  const englishValue = text.en?.trim() ?? "";

  return preferredValue || ukrainianValue || englishValue;
}

export function getLocalizedTextVariants(text: LocalizedText | null | undefined): string[] {
  if (!text) {
    return [];
  }

  return [...new Set([text.uk.trim(), text.en.trim()].filter(Boolean))];
}

export function buildLocalizedSearchText(text: LocalizedText | null | undefined): string {
  return getLocalizedTextVariants(text).join(" ").toLowerCase();
}

export function compareLocalizedText(left: LocalizedText, right: LocalizedText, language: string): number {
  return getLocalizedText(left, language).localeCompare(getLocalizedText(right, language));
}
