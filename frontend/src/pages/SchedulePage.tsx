import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMoviesRequest, getScheduleRequest } from "@/api/schedule";
import { useScheduleQueryParams } from "@/hooks/useScheduleQueryParams";
import type { Movie, ScheduleItem } from "@/types/domain";
import { ScheduleList } from "@/widgets/schedule/ScheduleList";
import { ScheduleToolbar } from "@/widgets/schedule/ScheduleToolbar";

export function SchedulePage() {
  const { t } = useTranslation();
  const { values, updateParam } = useScheduleQueryParams();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    void getScheduleRequest({
      sortBy: values.sortBy,
      sortOrder: values.sortOrder,
      movieId: values.movieId || undefined,
      limit: values.limit,
      offset: values.offset,
    })
      .then((response) => {
        setItems(response.data);
        setErrorMessage("");
      })
      .catch(() => {
        setItems([]);
        setErrorMessage(t("backendScheduleUnavailable"));
      });
  }, [t, values.limit, values.movieId, values.offset, values.sortBy, values.sortOrder]);

  useEffect(() => {
    void getMoviesRequest()
      .then((response) => {
        setMovies(response.data);
      })
      .catch(() => {
        setMovies([]);
      });
  }, []);

  const movieOptions = useMemo(
    () => movies.map((movie) => ({ id: movie.id, title: movie.title })),
    [movies],
  );

  return (
    <>
      <section>
        <h1 className="page-title">{t("schedule")}</h1>
        <p className="muted">{t("scheduleQueryHint")}</p>
      </section>
      <ScheduleToolbar
        sortBy={values.sortBy}
        sortOrder={values.sortOrder}
        movieId={values.movieId}
        movies={movieOptions}
        onChange={updateParam}
      />
      {errorMessage ? <section className="empty-state">{errorMessage}</section> : null}
      <ScheduleList items={items} />
    </>
  );
}
