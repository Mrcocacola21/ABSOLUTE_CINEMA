import { useTranslation } from "react-i18next";

function buildPageButtons(page: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, page - 1, page, page + 1]);

  if (page <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }

  if (page >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }

  const sortedPages = [...pages]
    .filter((value) => value >= 1 && value <= totalPages)
    .sort((left, right) => left - right);
  const result: Array<number | "ellipsis"> = [];

  for (const currentPage of sortedPages) {
    const lastItem = result[result.length - 1];
    if (typeof lastItem === "number" && currentPage - lastItem > 1) {
      result.push("ellipsis");
    }

    result.push(currentPage);
  }

  return result;
}

interface PaginationControlsProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export function PaginationControls({
  page,
  totalPages,
  onPageChange,
  className = "",
}: PaginationControlsProps) {
  const { t } = useTranslation();

  if (totalPages <= 1) {
    return null;
  }

  const pageButtons = buildPageButtons(page, totalPages);
  const classes = ["pagination-controls", className].filter(Boolean).join(" ");

  return (
    <nav className={classes} aria-label={t("common.pagination.label")}>
      <button
        className="button--ghost pagination-controls__nav"
        type="button"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        {t("common.pagination.previous")}
      </button>

      <div className="pagination-controls__group">
        <div className="pagination-controls__pages">
          {pageButtons.map((item, index) =>
            item === "ellipsis" ? (
              <span key={`ellipsis-${index}`} className="pagination-controls__ellipsis" aria-hidden="true">
                ...
              </span>
            ) : (
              <button
                key={item}
                className={`button--ghost pagination-controls__page${item === page ? " is-active" : ""}`}
                type="button"
                aria-current={item === page ? "page" : undefined}
                aria-label={t("common.pagination.goToPage", { page: item })}
                onClick={() => onPageChange(item)}
              >
                {item}
              </button>
            ),
          )}
        </div>

        <span className="pagination-controls__label">
          {t("common.pagination.pageIndicator", { current: page, total: totalPages })}
        </span>
      </div>

      <button
        className="button--ghost pagination-controls__nav"
        type="button"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        {t("common.pagination.next")}
      </button>
    </nav>
  );
}
