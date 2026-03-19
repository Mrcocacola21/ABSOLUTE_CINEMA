import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/widgets/layout/AppLayout";
import { ProtectedRoute } from "@/router/ProtectedRoute";
import { AdminDashboardPage } from "@/pages/AdminDashboardPage";
import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RegisterPage } from "@/pages/RegisterPage";
import { SchedulePage } from "@/pages/SchedulePage";
import { SessionDetailsPage } from "@/pages/SessionDetailsPage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/schedule/:sessionId" element={<SessionDetailsPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
          <Route element={<ProtectedRoute requiredRole="admin" />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
