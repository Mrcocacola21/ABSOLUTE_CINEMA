import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <section className="panel">
      <h1 className="page-title">{t("common.empty.notFound")}</h1>
      <Link to="/" className="button">
        {t("common.navigation.home")}
      </Link>
    </section>
  );
}
