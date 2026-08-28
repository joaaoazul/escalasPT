/**
 * AuthLayout — centred shell for the login screen.
 */

import { Outlet } from 'react-router-dom';
import { NotebookPen } from 'lucide-react';
import './AuthLayout.css';

export function AuthLayout() {
  return (
    <div className="auth-layout">
      <div className="auth-bg-orb auth-bg-orb-1" />
      <div className="auth-bg-orb auth-bg-orb-2" />
      <div className="auth-bg-grid" />

      <div className="auth-container animate-scale-in">
        <div className="auth-header">
          <div className="auth-logo">
            <NotebookPen size={28} strokeWidth={2} />
          </div>
          <h1 className="auth-title">Caderno de Serviço</h1>
          <p className="auth-subtitle">Registo de actividade no terreno</p>
        </div>
        <Outlet />
      </div>

      <footer className="auth-footer">
        <p>Guarda Nacional Republicana — utilização interna</p>
      </footer>
    </div>
  );
}
