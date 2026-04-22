import { useEffect, useMemo, useRef, useState } from "react";

export function getTotalPages(totalItems: number, pageSize: number): number {
  return Math.max(1, Math.ceil(totalItems / pageSize));
}

export function clampPage(page: number, totalPages: number): number {
  return Math.min(Math.max(page, 1), Math.max(totalPages, 1));
}

export function getPageItems<T>(items: T[], page: number, pageSize: number): T[] {
  const startIndex = (page - 1) * pageSize;
  return items.slice(startIndex, startIndex + pageSize);
}

interface UsePaginationOptions {
  pageSize: number;
  resetKey?: string;
}

export function usePagination<T>(items: T[], options: UsePaginationOptions) {
  const { pageSize, resetKey } = options;
  const [page, setPage] = useState(1);
  const lastResetKeyRef = useRef(resetKey);

  const totalPages = useMemo(() => getTotalPages(items.length, pageSize), [items.length, pageSize]);
  const shouldResetPage = resetKey !== undefined && lastResetKeyRef.current !== resetKey;
  const safePage = shouldResetPage ? 1 : clampPage(page, totalPages);

  useEffect(() => {
    if (shouldResetPage) {
      lastResetKeyRef.current = resetKey;
      setPage(1);
    }
  }, [resetKey, shouldResetPage]);

  useEffect(() => {
    if (!shouldResetPage) {
      setPage((currentPage) => clampPage(currentPage, totalPages));
    }
  }, [shouldResetPage, totalPages]);

  const pageItems = useMemo(() => getPageItems(items, safePage, pageSize), [items, pageSize, safePage]);

  return {
    page: safePage,
    setPage,
    totalPages,
    pageItems,
  };
}
