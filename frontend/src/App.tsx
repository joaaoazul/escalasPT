import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './layouts/AppLayout';
import { AuthLayout } from './layouts/AuthLayout';
import { HojePage } from './pages/HojePage';
import { LoginPage } from './pages/LoginPage';
import {
  AdminPage,
  PainelPage,
  RegistosPage,
  ServicosPage,
} from './pages/PlaceholderPages';
import { QueryProvider } from './providers/QueryProvider';
import { useAuthStore } from './store/authStore';

export default function App() {
  const restoreSession = useAuthStore((state) => state.restoreSession);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  return (
    <QueryProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<HojePage />} />
              <Route path="/servicos" element={<ServicosPage />} />
              <Route path="/registos" element={<RegistosPage />} />
              <Route path="/painel" element={<PainelPage />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route element={<AppLayout />}>
              <Route path="/admin" element={<AdminPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" theme="dark" richColors closeButton />
    </QueryProvider>
  );
}
