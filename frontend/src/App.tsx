/**
 * App root — React Router with protected routes per role.
 */

import { useEffect } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { useAuth } from './hooks/useAuth';
import { WebSocketProvider } from './providers/WebSocketProvider';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthLayout } from './layouts/AuthLayout';
import { AppLayout } from './layouts/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { SchedulePage } from './pages/SchedulePage';
import { StationSchedulePage } from './pages/StationSchedulePage';
import {
  UnauthorizedPage,
  NotFoundPage,
} from './pages/PlaceholderPages';
import { NotificationsPage } from './pages/NotificationsPage';
import { SwapsPage } from './pages/SwapsPage';
import { UsersPage } from './pages/UsersPage';
import { StationsPage } from './pages/StationsPage';
import { DashboardPage } from './pages/DashboardPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { AdminUsersPage } from './pages/AdminUsersPage';
import { AdminStationsPage } from './pages/AdminStationsPage';
import { AdminShiftTypesPage } from './pages/AdminShiftTypesPage';
import { AdminAuditLogPage } from './pages/AdminAuditLogPage';
import { AdminSessionsPage } from './pages/AdminSessionsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2, // 2 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppRoutes() {
  const { loadUser, isLoading } = useAuth();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  if (isLoading) {
    return (
      <div className="page-loader">
        <div style={{
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 'var(--space-4)',
        }}>
          <div className="spinner spinner-lg" />
          <span style={{
            color: 'var(--text-tertiary)', fontSize: 'var(--font-sm)',
            letterSpacing: '0.04em', textTransform: 'uppercase',
          }}>
            A carregar...
          </span>
        </div>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public — Auth */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Protected — All authenticated users */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          {/* Shared routes */}
          <Route path="/app/notifications" element={<NotificationsPage />} />

          {/* Militar + Comandante + Adjunto + Secretaria routes */}
          <Route element={<ProtectedRoute allowedRoles={['militar', 'comandante', 'adjunto', 'secretaria']} />}>
            <Route path="/app/schedule" element={<SchedulePage />} />
            <Route path="/app/station-schedule" element={<StationSchedulePage />} />
            <Route path="/app/swaps" element={<SwapsPage />} />
          </Route>

          {/* Comandante + Adjunto */}
          <Route element={<ProtectedRoute allowedRoles={['comandante', 'adjunto']} />}>
            <Route path="/app/dashboard" element={<DashboardPage />} />
          </Route>

          {/* Admin only */}
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/app/users" element={<UsersPage />} />
            <Route path="/app/stations" element={<StationsPage />} />
            <Route path="/app/admin" element={<AdminDashboardPage />} />
            <Route path="/app/admin/users" element={<AdminUsersPage />} />
            <Route path="/app/admin/stations" element={<AdminStationsPage />} />
            <Route path="/app/admin/shift-types" element={<AdminShiftTypesPage />} />
            <Route path="/app/admin/audit-log" element={<AdminAuditLogPage />} />
            <Route path="/app/admin/sessions" element={<AdminSessionsPage />} />
          </Route>
        </Route>
      </Route>

      {/* Error pages */}
      <Route path="/unauthorized" element={<UnauthorizedPage />} />

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/app" element={<Navigate to="/app/schedule" replace />} />

      {/* 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <WebSocketProvider>
          <AppRoutes />
          <Toaster
            position="top-right"
            theme="dark"
            richColors
            closeButton
            gap={8}
            toastOptions={{
              duration: 4000,
              style: {
                fontFamily: 'var(--font-family)',
              },
            }}
          />
        </WebSocketProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
