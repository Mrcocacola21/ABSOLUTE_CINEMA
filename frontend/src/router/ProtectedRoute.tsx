import { Link, Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { StatePanel } from "@/shared/ui/StatePanel";
import type { UserRole } from "@/types/domain";

interface ProtectedRouteProps {
  requiredRole?: UserRole;
}

export function ProtectedRoute({ requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, isAuthLoading, role } = useAuth();

  if (isAuthLoading) {
    return (
      <StatePanel
        tone="loading"
        title="Checking your session"
        message="Please wait while your account access is being confirmed."
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          statusMessage: "Sign in to continue.",
        }}
      />
    );
  }

  if (requiredRole && role !== requiredRole) {
    return (
      <StatePanel
        tone="error"
        title="Access denied"
        message="Administrator access is required to open this page."
        action={
          <Link to="/" className="button--ghost">
            Back home
          </Link>
        }
      />
    );
  }

  return <Outlet />;
}
