import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { StatePanel } from "@/shared/ui/StatePanel";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <StatePanel
      tone="empty"
      title={t("common.empty.notFound")}
      message={t("common.empty.notFoundText")}
      action={
        <Link to="/" className="button">
          {t("common.navigation.home")}
        </Link>
      }
    />
  );
}
