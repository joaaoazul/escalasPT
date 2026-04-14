/**
 * AdminSessionsPage — View and revoke active user sessions.
 */

import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldAlert, Lock, ChevronLeft, ChevronRight,
  Monitor, Clock, XCircle,
} from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { fetchSessions, revokeSession } from '../api/admin';
import { fetchUsers } from '../api/users';
import './AdminPages.css';

export function AdminSessionsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [activeOnly, setActiveOnly] = useState(true);
  const PAGE_SIZE = 30;

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-sessions', page, activeOnly],
    queryFn: () => fetchSessions({ active_only: activeOnly, skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
    staleTime: 1000 * 15,
  });

  const { data: usersData } = useQuery({
    queryKey: ['admin-users-map'],
    queryFn: () => fetchUsers({ limit: 500 }),
    staleTime: 1000 * 60 * 5,
  });

  const userMap = useMemo(() => {
    const map: Record<string, string> = {};
    usersData?.users.forEach(u => { map[u.id] = u.full_name; });
    return map;
  }, [usersData]);

  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE);

  const revokeMutation = useMutation({
    mutationFn: (sessionId: string) => revokeSession(sessionId),
    onSuccess: () => {
      toast.success('Sessão revogada');
      queryClient.invalidateQueries({ queryKey: ['admin-sessions'] });
    },
    onError: () => toast.error('Erro ao revogar sessão'),
  });

  function parseBrowser(ua: string | null): string {
    if (!ua) return '—';
    if (ua.includes('Firefox')) return 'Firefox';
    if (ua.includes('Edg')) return 'Edge';
    if (ua.includes('Chrome')) return 'Chrome';
    if (ua.includes('Safari')) return 'Safari';
    return ua.slice(0, 30);
  }

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Sessões Ativas</h1>
          <p className="page-subtitle">{data?.total || 0} sessões {activeOnly ? 'ativas' : 'totais'}.</p>
        </div>
        <label className="admin-toggle-label">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={e => { setActiveOnly(e.target.checked); setPage(0); }}
          />
          Apenas ativas
        </label>
      </div>

      <div className="admin-table-container">
        {isLoading ? (
          <div className="page-loader"><div className="spinner" /></div>
        ) : error ? (
          <div className="empty-state">
            <ShieldAlert size={40} className="text-danger" />
            <p>Erro ao carregar sessões.</p>
          </div>
        ) : (
          <>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Utilizador</th>
                  <th>IP</th>
                  <th>Browser</th>
                  <th>Criada</th>
                  <th>Última Atividade</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {(data?.sessions || []).map(s => (
                  <tr key={s.id}>
                    <td className="fw-bold">{userMap[s.user_id] || s.user_id.slice(0, 8)}</td>
                    <td className="text-muted" style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {s.ip_address || '—'}
                    </td>
                    <td>
                      <span className="state-badge" style={{ color: 'var(--text-secondary)' }}>
                        <Monitor size={14} /> {parseBrowser(s.user_agent)}
                      </span>
                    </td>
                    <td className="text-muted" style={{ fontSize: '0.75rem' }}>
                      {format(new Date(s.created_at), 'dd/MM HH:mm')}
                    </td>
                    <td className="text-muted" style={{ fontSize: '0.75rem' }}>
                      {s.last_seen_at ? format(new Date(s.last_seen_at), 'dd/MM HH:mm') : '—'}
                    </td>
                    <td>
                      {s.is_revoked ? (
                        <span className="state-badge text-danger"><XCircle size={14} /> Revogada</span>
                      ) : (
                        <span className="state-badge text-success"><Lock size={14} /> Ativa</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {!s.is_revoked && (
                        <button
                          className="btn btn-ghost btn-sm text-danger"
                          onClick={() => revokeMutation.mutate(s.session_id)}
                          disabled={revokeMutation.isPending}
                        >
                          Revogar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {(data?.sessions || []).length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                      Sem sessões encontradas.
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
