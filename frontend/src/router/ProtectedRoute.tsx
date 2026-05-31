import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/useAuth";
import { rememberProtectedRedirect } from "@/shared/storage";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { UserRole } from "@/types/domain";

interface ProtectedRouteProps {
  requiredRole?: UserRole;
  redirectOnRoleMismatch?: string;
}

export function ProtectedRoute({ requiredRole, redirectOnRoleMismatch }: ProtectedRouteProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isAuthLoading, role } = useAuth();
  const location = useLocation();
  const from = `${location.pathname}${location.search}`;

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      rememberProtectedRedirect(from);
    }
  }, [from, isAuthenticated, isAuthLoading]);

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
          from,
        }}
      />
    );
  }

  if (requiredRole && role !== requiredRole) {
    if (redirectOnRoleMismatch) {
      return <Navigate to={redirectOnRoleMismatch} replace />;
    }

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
