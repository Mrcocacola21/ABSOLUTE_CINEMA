import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import type { UserRole } from "@/types/domain";

interface ProtectedRouteProps {
  requiredRole?: UserRole;
}

export function ProtectedRoute({ requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, role } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && role !== requiredRole) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
