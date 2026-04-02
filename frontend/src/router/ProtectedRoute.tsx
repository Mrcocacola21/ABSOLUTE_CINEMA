import { Link, Navigate, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/features/auth/useAuth";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { UserRole } from "@/types/domain";

interface ProtectedRouteProps {
  requiredRole?: UserRole;
}

export function ProtectedRoute({ requiredRole }: ProtectedRouteProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isAuthLoading, role } = useAuth();

  if (isAuthLoading) {
    return (
      <StatePanel
        tone="loading"
        title={t("auth.protected.checkingTitle")}
        message={t("auth.protected.checkingMessage")}
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          statusMessage: t("auth.prompts.signInToContinue"),
        }}
      />
    );
  }

  if (requiredRole && role !== requiredRole) {
    return (
      <StatePanel
        tone="error"
        title={t("auth.protected.accessDeniedTitle")}
        message={t("auth.protected.accessDeniedMessage")}
        action={
          <Link to="/" className="button--ghost">
            {t("common.navigation.home")}
          </Link>
        }
      />
    );
  }

  return <Outlet />;
}
