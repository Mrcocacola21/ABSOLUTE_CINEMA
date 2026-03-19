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

  return {
    searchParams,
    updateParam,
    values: {
      sortBy: searchParams.get("sortBy") ?? DEFAULT_SCHEDULE_PARAMS.sortBy,
      sortOrder: searchParams.get("sortOrder") ?? DEFAULT_SCHEDULE_PARAMS.sortOrder,
      movieId: searchParams.get("movieId") ?? "",
      limit: searchParams.get("limit") ?? DEFAULT_SCHEDULE_PARAMS.limit,
      offset: searchParams.get("offset") ?? DEFAULT_SCHEDULE_PARAMS.offset,
    },
  };
}
