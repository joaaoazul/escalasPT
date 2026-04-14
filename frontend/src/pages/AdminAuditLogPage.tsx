/**
 * AdminAuditLogPage — Full audit trail viewer with filters.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldAlert, ChevronLeft, ChevronRight,
  Eye, FileText, Clock, User as UserIcon,
} from 'lucide-react';
import { format } from 'date-fns';
import { fetchAuditLogs, type AuditLogFilters } from '../api/admin';
import './AdminPages.css';

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  create: { label: 'CRIAR', color: 'var(--color-primary-500)' },
  update: { label: 'ATUALIZAR', color: 'var(--color-info-500)' },
  delete: { label: 'ELIMINAR', color: 'var(--color-danger-500)' },
  login: { label: 'LOGIN', color: 'var(--color-accent-500)' },
  logout: { label: 'LOGOUT', color: 'var(--text-tertiary)' },
  publish: { label: 'PUBLICAR', color: 'var(--color-primary-400)' },
  password_reset: { label: 'RESET PW', color: 'var(--color-warning-500)' },
  revoke_session: { label: 'REVOGAR', color: 'var(--color-danger-400)' },
  revoke_all_sessions: { label: 'REVOGAR TUDO', color: 'var(--color-danger-500)' },
  unlock_account: { label: 'DESBLOQUEAR', color: 'var(--color-primary-400)' },
  swap_approve: { label: 'APROVAR TROCA', color: 'var(--color-primary-500)' },
  swap_reject: { label: 'REJEITAR TROCA', color: 'var(--color-danger-400)' },
  anonymize: { label: 'ANONIMIZAR', color: 'var(--color-warning-500)' },
};

const RESOURCE_LABELS: Record<string, string> = {
  user: 'Utilizador',
  station: 'Posto',
  shift: 'Turno',
  shift_type: 'Tipo de Turno',
  session: 'Sessão',
  swap: 'Troca',
  notification: 'Notificação',
};

export function AdminAuditLogPage() {
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState<AuditLogFilters>({});
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const PAGE_SIZE = 30;

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-audit-logs', page, filters],
    queryFn: () => fetchAuditLogs({ ...filters, skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
    staleTime: 1000 * 15,
  });

  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE);

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Registo de Auditoria</h1>
          <p className="page-subtitle">{data?.total || 0} entradas registadas.</p>
        </div>
      </div>

      <div className="admin-toolbar">
        <div className="admin-filters">
          <select
            value={filters.action || ''}
            onChange={e => { setFilters(f => ({ ...f, action: e.target.value || undefined })); setPage(0); }}
          >
            <option value="">Todas as ações</option>
            {Object.keys(ACTION_LABELS).map(a => (
              <option key={a} value={a}>{ACTION_LABELS[a]?.label}</option>
            ))}
          </select>
          <select
            value={filters.resource_type || ''}
            onChange={e => { setFilters(f => ({ ...f, resource_type: e.target.value || undefined })); setPage(0); }}
          >
            <option value="">Todos os recursos</option>
            {Object.keys(RESOURCE_LABELS).map(r => (
              <option key={r} value={r}>{RESOURCE_LABELS[r]}</option>
            ))}
          </select>
          <input
            type="date"
            value={filters.date_from || ''}
            onChange={e => { setFilters(f => ({ ...f, date_from: e.target.value || undefined })); setPage(0); }}
            title="Data início"
          />
          <input
            type="date"
            value={filters.date_to || ''}
            onChange={e => { setFilters(f => ({ ...f, date_to: e.target.value || undefined })); setPage(0); }}
            title="Data fim"
          />
        </div>
      </div>

      <div className="admin-table-container">
        {isLoading ? (
          <div className="page-loader"><div className="spinner" /></div>
        ) : error ? (
          <div className="empty-state">
            <ShieldAlert size={40} className="text-danger" />
            <p>Erro ao carregar auditoria.</p>
          </div>
        ) : (
          <>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Data/Hora</th>
                  <th>Ação</th>
                  <th>Recurso</th>
                  <th>ID Recurso</th>
                  <th>IP</th>
                  <th style={{ textAlign: 'right' }}>Detalhes</th>
                </tr>
              </thead>
              <tbody>
                {(data?.logs || []).map(log => {
                  const actionMeta = ACTION_LABELS[log.action] || { label: log.action.toUpperCase(), color: 'var(--text-tertiary)' };
                  const isExpanded = expandedLog === log.id;

                  return (
                    <>
                      <tr key={log.id} className={isExpanded ? 'audit-row-expanded' : ''}>
                        <td>
                          <span className="state-badge" style={{ color: 'var(--text-secondary)' }}>
                            <Clock size={13} />
                            {format(new Date(log.created_at), 'dd/MM/yyyy HH:mm:ss')}
                          </span>
                        </td>
                        <td>
                          <span
                            className="badge"
                            style={{ background: `${actionMeta.color}20`, color: actionMeta.color }}
                          >
                            {actionMeta.label}
                          </span>
                        </td>
                        <td className="text-muted">
                          {RESOURCE_LABELS[log.resource_type] || log.resource_type}
                        </td>
                        <td>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
                            {log.resource_id ? log.resource_id.slice(0, 8) + '...' : '—'}
                          </span>
                        </td>
                        <td className="text-muted" style={{ fontSize: '0.75rem' }}>
                          {log.ip_address || '—'}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            className="btn-icon"
                            onClick={() => setExpandedLog(isExpanded ? null : log.id)}
                            title="Ver detalhes"
                          >
                            <Eye size={16} />
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${log.id}-detail`} className="audit-detail-row">
                          <td colSpan={6}>
                            <div className="audit-detail-content">
                              {log.user_id && (
                                <div className="audit-detail-field">
                                  <UserIcon size={14} />
                                  <strong>User ID:</strong>
                                  <span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{log.user_id}</span>
                                </div>
                              )}
                              {log.user_agent && (
                                <div className="audit-detail-field">
                                  <FileText size={14} />
                                  <strong>User Agent:</strong>
                                  <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                                    {log.user_agent.slice(0, 100)}
                                  </span>
                                </div>
                              )}
                              {log.old_data && (
                                <div className="audit-detail-json">
                                  <strong>Dados Anteriores:</strong>
                                  <pre>{JSON.stringify(log.old_data, null, 2)}</pre>
                                </div>
                              )}
                              {log.new_data && (
                                <div className="audit-detail-json">
                                  <strong>Dados Novos:</strong>
                                  <pre>{JSON.stringify(log.new_data, null, 2)}</pre>
                                </div>
                              )}
                              {!log.old_data && !log.new_data && (
                                <span className="text-muted">Sem dados adicionais.</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
                {(data?.logs || []).length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                      Sem entradas de auditoria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="admin-pagination">
                <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                  <ChevronLeft size={16} /> Anterior
                </button>
                <span>Página {page + 1} de {totalPages}</span>
                <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>
                  Seguinte <ChevronRight size={16} />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
