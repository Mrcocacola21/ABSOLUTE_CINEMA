import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/widgets/layout/AppLayout";
import { ProtectedRoute } from "@/router/ProtectedRoute";
import { AdminAttendanceDetailsPage } from "@/pages/AdminAttendanceDetailsPage";
import { AdminDashboardPage } from "@/pages/AdminDashboardPage";
import { AdminOrderValidationPage } from "@/pages/AdminOrderValidationPage";
import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import { MovieDetailsPage } from "@/pages/MovieDetailsPage";
import { MoviesPage } from "@/pages/MoviesPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OrderDetailsPage } from "@/pages/OrderDetailsPage";
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
          <Route path="/movies" element={<MoviesPage />} />
          <Route path="/movies/:movieId" element={<MovieDetailsPage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/schedule/:sessionId" element={<SessionDetailsPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/me/orders/:orderId" element={<OrderDetailsPage />} />
          </Route>
          <Route element={<ProtectedRoute requiredRole="admin" />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/attendance/:sessionId" element={<AdminAttendanceDetailsPage />} />
            <Route path="/admin/order-validation" element={<AdminOrderValidationPage />} />
            <Route path="/admin/order-validation/:token" element={<AdminOrderValidationPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
