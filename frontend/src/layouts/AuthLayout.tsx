/**
 * AuthLayout — centered layout for login and auth pages.
 */

import { Outlet } from 'react-router-dom';
import { Shield } from 'lucide-react';
import './AuthLayout.css';

export function AuthLayout() {
  return (
    <div className="auth-layout">
      {/* Ambient background effects */}
      <div className="auth-bg-orb auth-bg-orb-1" />
      <div className="auth-bg-orb auth-bg-orb-2" />
      <div className="auth-bg-grid" />

      <div className="auth-container animate-scale-in">
        <div className="auth-header">
          <div className="auth-logo">
            <Shield size={28} strokeWidth={2} />
          </div>
          <h1 className="auth-title">EscalasPT</h1>
          <p className="auth-subtitle">Plataforma de Gestão de Escalas</p>
        </div>
        <Outlet />
      </div>

      <footer className="auth-footer">
        <p>Guarda Nacional Republicana — Sistema Interno</p>
      </footer>
    </div>
  );
}
