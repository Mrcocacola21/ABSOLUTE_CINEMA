interface PosterSource {
  poster_url?: string | null;
  poster_file_url?: string | null;
  poster_display_url?: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function getApiOrigin(): string {
  try {
    return new URL(API_BASE_URL, window.location.origin).origin;
  } catch {
    return "";
  }
}

function resolveBackendMediaUrl(value: string): string {
  if (!value.startsWith("/")) {
    return value;
  }

  const apiOrigin = getApiOrigin();
  return apiOrigin ? `${apiOrigin}${value}` : value;
}

export function resolvePosterSource(source: PosterSource): string | null {
  const selectedSource = source.poster_display_url ?? source.poster_file_url ?? source.poster_url ?? null;
  if (!selectedSource) {
    return null;
  }

  const isUploadedPoster =
    Boolean(source.poster_file_url) &&
    (selectedSource === source.poster_file_url || selectedSource === source.poster_display_url);

  return isUploadedPoster ? resolveBackendMediaUrl(selectedSource) : selectedSource;
}

export function getPosterBackgroundValue(source: PosterSource): string {
  const posterSource = resolvePosterSource(source);
  return posterSource ? `url("${posterSource}")` : "none";
}
