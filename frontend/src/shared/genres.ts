import { normalizeLanguageCode } from "@/shared/localization";

export const GENRE_CATALOG = {
  action: { uk: "Бойовик", en: "Action" },
  adventure: { uk: "Пригоди", en: "Adventure" },
  animation: { uk: "Анімація", en: "Animation" },
  biographical: { uk: "Біографічний", en: "Biographical" },
  comedy: { uk: "Комедія", en: "Comedy" },
  crime: { uk: "Кримінальний", en: "Crime" },
  detective: { uk: "Детектив", en: "Detective" },
  documentary: { uk: "Документальний", en: "Documentary" },
  drama: { uk: "Драма", en: "Drama" },
  family: { uk: "Сімейний", en: "Family" },
  fantasy: { uk: "Фентезі", en: "Fantasy" },
  historical: { uk: "Історичний", en: "Historical" },
  horror: { uk: "Жахи", en: "Horror" },
  melodrama: { uk: "Мелодрама", en: "Melodrama" },
  musical: { uk: "Мюзикл", en: "Musical" },
  mystery: { uk: "Містика", en: "Mystery" },
  romance: { uk: "Романтика", en: "Romance" },
  science_fiction: { uk: "Фантастика", en: "Science Fiction" },
  sport: { uk: "Спортивний", en: "Sport" },
  thriller: { uk: "Трилер", en: "Thriller" },
  war: { uk: "Воєнний", en: "War" },
  western: { uk: "Вестерн", en: "Western" },
} as const;

export type GenreCode = keyof typeof GENRE_CATALOG;

export const GENRE_OPTIONS = Object.entries(GENRE_CATALOG).map(([code, labels]) => ({
  code: code as GenreCode,
  labels,
}));

export function isGenreCode(value: string): value is GenreCode {
  return value in GENRE_CATALOG;
}

export function getGenreLabel(code: string, language: string): string {
  const genre = isGenreCode(code) ? GENRE_CATALOG[code] : null;
  if (!genre) {
    return code;
  }

  return genre[normalizeLanguageCode(language)] ?? genre.uk;
}

export function getGenreLabels(codes: readonly string[], language: string): string[] {
  return codes.map((code) => getGenreLabel(code, language));
}

export function buildGenreSearchText(code: string): string {
  const genre = isGenreCode(code) ? GENRE_CATALOG[code] : null;
  if (!genre) {
    return code.toLowerCase();
  }

  return [code, genre.uk, genre.en].join(" ").toLowerCase();
}
