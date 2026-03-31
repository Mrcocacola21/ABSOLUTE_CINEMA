import { useSearchParams } from "react-router-dom";

import { DEFAULT_SCHEDULE_PARAMS } from "@/shared/constants";

export function useScheduleQueryParams() {
  const [searchParams, setSearchParams] = useSearchParams(DEFAULT_SCHEDULE_PARAMS);

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (!value) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    if (key !== "offset") {
      next.set("offset", "0");
    }
    setSearchParams(next, { replace: true });
  }

  function updateParams(updates: Record<string, string>) {
    const next = new URLSearchParams(searchParams);
    let shouldResetOffset = false;

    for (const [key, value] of Object.entries(updates)) {
      if (!value) {
        next.delete(key);
      } else {
        next.set(key, value);
      }

      if (key !== "offset") {
        shouldResetOffset = true;
      }
    }

    if (shouldResetOffset) {
      next.set("offset", "0");
    }

    setSearchParams(next, { replace: true });
  }

  function resetParams() {
    setSearchParams(new URLSearchParams(DEFAULT_SCHEDULE_PARAMS), { replace: true });
  }

  return {
    searchParams,
    updateParam,
    updateParams,
    resetParams,
    values: {
      day: searchParams.get("day") ?? DEFAULT_SCHEDULE_PARAMS.day,
      genre: searchParams.get("genre") ?? DEFAULT_SCHEDULE_PARAMS.genre,
      listDay: searchParams.get("listDay") ?? DEFAULT_SCHEDULE_PARAMS.listDay,
      dateSort: searchParams.get("dateSort") ?? DEFAULT_SCHEDULE_PARAMS.dateSort,
      seatSort: searchParams.get("seatSort") ?? DEFAULT_SCHEDULE_PARAMS.seatSort,
      query: searchParams.get("query") ?? DEFAULT_SCHEDULE_PARAMS.query,
      movieId: searchParams.get("movieId") ?? "",
      sessionId: searchParams.get("sessionId") ?? "",
      limit: searchParams.get("limit") ?? DEFAULT_SCHEDULE_PARAMS.limit,
      offset: searchParams.get("offset") ?? DEFAULT_SCHEDULE_PARAMS.offset,
    },
  };
}
