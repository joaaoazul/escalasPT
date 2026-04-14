/**
 * AdminDashboardPage — System-wide overview with KPIs, activity, and quick actions.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Users, Building2, Calendar, Shield, Activity,
  TrendingUp, Lock, Eye,
} from 'lucide-react';
import { fetchSystemStats } from '../api/admin';
import './AdminPages.css';

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administradores',
  comandante: 'Comandantes',
  adjunto: 'Adjuntos',
  secretaria: 'Secretárias',
  militar: 'Militares',
};

const ROLE_COLORS: Record<string, string> = {
  admin: '#ef4444',
  comandante: '#f59e0b',
  adjunto: '#3b82f6',
  secretaria: '#10b981',
  militar: '#8b5cf6',
};

export function AdminDashboardPage() {
  const navigate = useNavigate();

  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: fetchSystemStats,
    staleTime: 1000 * 30,
  });

  if (isLoading) {
    return (
      <div className="page-container">
        <div className="page-loader"><div className="spinner" /></div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Painel de Administração</h1>
          <p className="page-subtitle">Visão global do sistema EscalasPT.</p>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="admin-kpi-grid">
        <div className="admin-kpi-card" onClick={() => navigate('/app/admin/users')}>
          <div className="admin-kpi-icon" style={{ background: 'var(--color-primary-500)' }}>
            <Users size={22} />
          </div>
          <div className="admin-kpi-body">
            <span className="admin-kpi-value">{stats.total_users}</span>
            <span className="admin-kpi-label">Utilizadores</span>
            <span className="admin-kpi-detail">{stats.active_users} ativos · {stats.inactive_users} inativos</span>
          </div>
        </div>

        <div className="admin-kpi-card" onClick={() => navigate('/app/admin/stations')}>
          <div className="admin-kpi-icon" style={{ background: 'var(--color-info-500)' }}>
            <Building2 size={22} />
          </div>
          <div className="admin-kpi-body">
            <span className="admin-kpi-value">{stats.total_stations}</span>
            <span className="admin-kpi-label">Postos</span>
            <span className="admin-kpi-detail">{stats.active_stations} ativos</span>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-icon" style={{ background: 'var(--color-accent-500)' }}>
            <Calendar size={22} />
          </div>
          <div className="admin-kpi-body">
            <span className="admin-kpi-value">{stats.total_shifts}</span>
            <span className="admin-kpi-label">Turnos</span>
            <span className="admin-kpi-detail">{stats.published_shifts} publicados · {stats.draft_shifts} rascunhos</span>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-icon" style={{ background: '#8b5cf6' }}>
            <Shield size={22} />
          </div>
          <div className="admin-kpi-body">
            <span className="admin-kpi-value">{stats.active_sessions}</span>
            <span className="admin-kpi-label">Sessões Ativas</span>
          </div>
        </div>

        <div className="admin-kpi-card">
          <div className="admin-kpi-icon" style={{ background: 'var(--color-warning-500)' }}>
            <TrendingUp size={22} />
          </div>
          <div className="admin-kpi-body">
            <span className="admin-kpi-value">{stats.shifts_last_30_days}</span>
            <span className="admin-kpi-label">Turnos (30 dias)</span>
          </div>
        </div>
      </div>

      {/* Bottom Sections */}
      <div className="admin-sections-grid">
        {/* Role Distribution */}
        <div className="admin-section-card">
          <h3 className="admin-section-title">
            <Users size={18} /> Distribuição por Função
          </h3>
          <div className="admin-role-bars">
            {Object.entries(stats.users_by_role).map(([role, count]) => {
              const pct = stats.total_users > 0 ? (count / stats.total_users) * 100 : 0;
              return (
                <div key={role} className="admin-role-bar-row">
                  <div className="admin-role-bar-label">
                    <span className="admin-role-dot" style={{ background: ROLE_COLORS[role] || '#64748b' }} />
                    {ROLE_LABELS[role] || role}
                  </div>
                  <div className="admin-role-bar-track">
                    <div
                      className="admin-role-bar-fill"
                      style={{ width: `${pct}%`, background: ROLE_COLORS[role] || '#64748b' }}
                    />
                  </div>
                  <span className="admin-role-bar-count">{count}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="admin-section-card">
          <h3 className="admin-section-title">
            <Activity size={18} /> Ações Rápidas
          </h3>
          <div className="admin-quick-actions">
            <button className="admin-action-btn" onClick={() => navigate('/app/admin/users')}>
              <Users size={18} /> Gerir Utilizadores
            </button>
            <button className="admin-action-btn" onClick={() => navigate('/app/admin/stations')}>
              <Building2 size={18} /> Gerir Postos
            </button>
            <button className="admin-action-btn" onClick={() => navigate('/app/admin/shift-types')}>
              <Calendar size={18} /> Tipos de Turno
            </button>
            <button className="admin-action-btn" onClick={() => navigate('/app/admin/audit-log')}>
              <Eye size={18} /> Registo de Auditoria
            </button>
            <button className="admin-action-btn" onClick={() => navigate('/app/admin/sessions')}>
              <Lock size={18} /> Sessões Ativas
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
