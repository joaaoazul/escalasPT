/**
 * AdminUsersPage — Full CRUD user management with create/edit modals,
 * password reset, session revocation, account unlock, anonymization.
 */

import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search, ShieldAlert, CheckCircle, XCircle, Plus,
  Edit, Trash2, Key, Lock, Unlock, UserX, X,
  ChevronLeft, ChevronRight, Filter,
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchUsers, createUser, updateUser, type UserCreateData, type UserUpdateData } from '../api/users';
import { fetchStations } from '../api/stations';
import { adminResetPassword, unlockUser, revokeAllUserSessions } from '../api/admin';
import type { User, UserRole } from '../types';
import './AdminPages.css';

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'admin', label: 'Administrador' },
  { value: 'comandante', label: 'Comandante' },
  { value: 'adjunto', label: 'Adjunto' },
  { value: 'secretaria', label: 'Secretária' },
  { value: 'militar', label: 'Militar' },
];

function roleBadgeClass(role: string): string {
  switch (role) {
    case 'admin': return 'badge-danger';
    case 'comandante': return 'badge-warning';
    case 'adjunto': return 'badge-primary';
    case 'secretaria': return 'badge-success';
    default: return 'badge-info';
  }
}

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [stationFilter, setStationFilter] = useState<string>('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [passwordResetUser, setPasswordResetUser] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [actionMenuUser, setActionMenuUser] = useState<string | null>(null);

  // Create form
  const [createForm, setCreateForm] = useState<UserCreateData>({
    username: '', email: '', password: '', full_name: '', nip: '', role: 'militar',
  });

  // Edit form
  const [editForm, setEditForm] = useState<UserUpdateData>({});

  const { data: usersData, isLoading, error } = useQuery({
    queryKey: ['admin-users', page, roleFilter, statusFilter, stationFilter],
    queryFn: () => fetchUsers({
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      role: roleFilter || undefined,
      is_active: statusFilter === '' ? undefined : statusFilter === 'true',
      station_id: stationFilter || undefined,
    }),
    staleTime: 1000 * 30,
  });

  const { data: stationsData } = useQuery({
    queryKey: ['stations-all'],
    queryFn: () => fetchStations({ limit: 200 }),
    staleTime: 1000 * 60 * 10,
  });

  const stations = stationsData?.stations || [];
  const stationMap = useMemo(() => {
    const map: Record<string, string> = {};
    stations.forEach(s => { map[s.id] = s.name; });
    return map;
  }, [stations]);

  const filteredUsers = usersData?.users.filter(u =>
    u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.nip.includes(searchTerm) ||
    (u.numero_ordem && u.numero_ordem.includes(searchTerm))
  ) || [];

  const totalPages = Math.ceil((usersData?.total || 0) / PAGE_SIZE);

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: UserCreateData) => createUser(data),
    onSuccess: () => {
      toast.success('Utilizador criado com sucesso');
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setShowCreateModal(false);
      setCreateForm({ username: '', email: '', password: '', full_name: '', nip: '', role: 'militar' });
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Erro ao criar utilizador'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdateData }) => updateUser(id, data),
    onSuccess: () => {
      toast.success('Utilizador atualizado');
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setEditingUser(null);
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Erro ao atualizar'),
  });

  const resetPasswordMutation = useMutation({
    mutationFn: ({ id, pw }: { id: string; pw: string }) => adminResetPassword(id, pw),
    onSuccess: () => {
      toast.success('Password redefinida');
      setPasswordResetUser(null);
      setNewPassword('');
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Erro ao redefinir password'),
  });

  const unlockMutation = useMutation({
    mutationFn: (id: string) => unlockUser(id),
    onSuccess: () => {
      toast.success('Conta desbloqueada');
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: () => toast.error('Erro ao desbloquear'),
  });

  const revokeSessionsMutation = useMutation({
    mutationFn: (id: string) => revokeAllUserSessions(id),
    onSuccess: () => toast.success('Sessões revogadas'),
    onError: () => toast.error('Erro ao revogar sessões'),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      updateUser(id, { is_active: active }),
    onSuccess: (_, { active }) => {
      toast.success(active ? 'Utilizador ativado' : 'Utilizador desativado');
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: () => toast.error('Erro ao alterar estado'),
  });

  const openEdit = (user: User) => {
    setEditForm({
      email: user.email,
      full_name: user.full_name,
      numero_ordem: user.numero_ordem || undefined,
      phone: user.phone || undefined,
      role: user.role,
      station_id: user.station_id || undefined,
      is_active: user.is_active,
    });
    setEditingUser(user);
    setActionMenuUser(null);
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Gestão de Utilizadores</h1>
          <p className="page-subtitle">{usersData?.total || 0} utilizadores registados no sistema.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={16} /> Criar Utilizador
        </button>
      </div>

      {/* Filters */}
      <div className="admin-toolbar">
        <div className="search-bar">
          <Search size={18} />
          <input
            type="text"
            placeholder="Pesquisar por nome, username ou NIP..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="admin-filters">
          <select value={roleFilter} onChange={e => { setRoleFilter(e.target.value); setPage(0); }}>
            <option value="">Todas as funções</option>
            {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(0); }}>
            <option value="">Todos os estados</option>
            <option value="true">Ativos</option>
            <option value="false">Inativos</option>
          </select>
          <select value={stationFilter} onChange={e => { setStationFilter(e.target.value); setPage(0); }}>
            <option value="">Todos os postos</option>
            {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="admin-table-container">
        {isLoading ? (
          <div className="page-loader"><div className="spinner" /></div>
        ) : error ? (
          <div className="empty-state">
            <ShieldAlert size={40} className="text-danger" />
            <p>Erro ao carregar utilizadores.</p>
          </div>
        ) : (
          <>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Username</th>
                  <th>Posto</th>
                  <th>Função</th>
                  <th>Estado</th>
                  <th>2FA</th>
                  <th style={{ textAlign: 'right' }}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => (
                  <tr key={u.id}>
                    <td className="fw-bold">
                      {u.full_name}
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginLeft: '8px' }}>
                        NIP {u.nip}
                        {u.numero_ordem && <> · N.º {u.numero_ordem}</>}
                      </span>
                    </td>
                    <td>{u.username}</td>
                    <td className="text-muted">{u.station_id ? stationMap[u.station_id] || '—' : '—'}</td>
                    <td>
                      <span className={`badge ${roleBadgeClass(u.role)}`}>
                        {u.role.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      {u.is_active ? (
                        <span className="state-badge text-success"><CheckCircle size={14} /> Ativo</span>
                      ) : (
                        <span className="state-badge text-danger"><XCircle size={14} /> Inativo</span>
                      )}
                    </td>
                    <td>
                      {u.totp_enabled ? (
                        <span className="state-badge text-success"><Lock size={14} /></span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right', position: 'relative' }}>
                      <button
                        className="btn-icon"
                        onClick={() => setActionMenuUser(actionMenuUser === u.id ? null : u.id)}
                      >
                        <Edit size={16} />
                      </button>
                      {actionMenuUser === u.id && (
                        <div className="admin-action-dropdown">
                          <button onClick={() => openEdit(u)}>
                            <Edit size={14} /> Editar
                          </button>
                          <button onClick={() => { setPasswordResetUser(u); setActionMenuUser(null); }}>
                            <Key size={14} /> Reset Password
                          </button>
                          <button onClick={() => { unlockMutation.mutate(u.id); setActionMenuUser(null); }}>
                            <Unlock size={14} /> Desbloquear
                          </button>
                          <button onClick={() => { revokeSessionsMutation.mutate(u.id); setActionMenuUser(null); }}>
                            <Lock size={14} /> Revogar Sessões
                          </button>
                          <hr />
                          <button
                            className="text-danger"
                            onClick={() => {
                              toggleActiveMutation.mutate({ id: u.id, active: !u.is_active });
                              setActionMenuUser(null);
                            }}
                          >
                            {u.is_active ? <><XCircle size={14} /> Desativar</> : <><CheckCircle size={14} /> Ativar</>}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {filteredUsers.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                      Sem resultados encontrados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Pagination */}
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

      {/* Create Modal */}
      {showCreateModal && (
        <div className="admin-modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="admin-modal" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2>Criar Utilizador</h2>
              <button className="btn-icon" onClick={() => setShowCreateModal(false)}><X size={20} /></button>
            </div>
            <form
              className="admin-modal-body"
              onSubmit={e => { e.preventDefault(); createMutation.mutate(createForm); }}
            >
              <div className="admin-form-grid">
                <label>
                  <span>Nome Completo *</span>
                  <input
                    required
                    value={createForm.full_name}
                    onChange={e => setCreateForm(f => ({ ...f, full_name: e.target.value }))}
                  />
                </label>
                <label>
                  <span>NIP *</span>
                  <input
                    required
                    value={createForm.nip}
                    onChange={e => setCreateForm(f => ({ ...f, nip: e.target.value }))}
                  />
                </label>
                <label>
                  <span>N.º Ordem</span>
                  <input
                    value={createForm.numero_ordem || ''}
                    onChange={e => setCreateForm(f => ({ ...f, numero_ordem: e.target.value }))}
                    placeholder="Ex: 1234"
                    maxLength={10}
                  />
                </label>
                <label>
                  <span>Username *</span>
                  <input
                    required
                    value={createForm.username}
                    onChange={e => setCreateForm(f => ({ ...f, username: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Email *</span>
                  <input
                    required
                    type="email"
                    value={createForm.email}
                    onChange={e => setCreateForm(f => ({ ...f, email: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Password * (mín. 12 caract.)</span>
                  <input
                    required
                    type="password"
                    minLength={12}
                    value={createForm.password}
                    onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Telefone</span>
                  <input
                    value={createForm.phone || ''}
                    onChange={e => setCreateForm(f => ({ ...f, phone: e.target.value || undefined }))}
                  />
                </label>
                <label>
                  <span>Função *</span>
                  <select
                    value={createForm.role || 'militar'}
                    onChange={e => setCreateForm(f => ({ ...f, role: e.target.value as UserRole }))}
                  >
                    {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Posto</span>
                  <select
                    value={createForm.station_id || ''}
                    onChange={e => setCreateForm(f => ({ ...f, station_id: e.target.value || undefined }))}
                  >
                    <option value="">Sem posto</option>
                    {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'A criar...' : 'Criar Utilizador'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingUser && (
        <div className="admin-modal-overlay" onClick={() => setEditingUser(null)}>
          <div className="admin-modal" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2>Editar — {editingUser.full_name}</h2>
              <button className="btn-icon" onClick={() => setEditingUser(null)}><X size={20} /></button>
            </div>
            <form
              className="admin-modal-body"
              onSubmit={e => { e.preventDefault(); updateMutation.mutate({ id: editingUser.id, data: editForm }); }}
            >
              <div className="admin-form-grid">
                <label>
                  <span>Nome Completo</span>
                  <input
                    value={editForm.full_name || ''}
                    onChange={e => setEditForm(f => ({ ...f, full_name: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Email</span>
                  <input
                    type="email"
                    value={editForm.email || ''}
                    onChange={e => setEditForm(f => ({ ...f, email: e.target.value }))}
                  />
                </label>
                <label>
                  <span>N.º Ordem</span>
                  <input
                    value={editForm.numero_ordem || ''}
                    onChange={e => setEditForm(f => ({ ...f, numero_ordem: e.target.value || undefined }))}
                    placeholder="Ex: 1234"
                    maxLength={10}
                  />
                </label>
                <label>
                  <span>Telefone</span>
                  <input
                    value={editForm.phone || ''}
                    onChange={e => setEditForm(f => ({ ...f, phone: e.target.value || undefined }))}
                  />
                </label>
                <label>
                  <span>Função</span>
                  <select
                    value={editForm.role || ''}
                    onChange={e => setEditForm(f => ({ ...f, role: e.target.value as UserRole }))}
                  >
                    {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Posto</span>
                  <select
                    value={editForm.station_id || ''}
                    onChange={e => setEditForm(f => ({ ...f, station_id: e.target.value || undefined }))}
                  >
                    <option value="">Sem posto</option>
                    {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
                <label>
                  <span>Estado</span>
                  <select
                    value={editForm.is_active ? 'true' : 'false'}
                    onChange={e => setEditForm(f => ({ ...f, is_active: e.target.value === 'true' }))}
                  >
                    <option value="true">Ativo</option>
                    <option value="false">Inativo</option>
                  </select>
                </label>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setEditingUser(null)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? 'A guardar...' : 'Guardar Alterações'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Password Reset Modal */}
      {passwordResetUser && (
        <div className="admin-modal-overlay" onClick={() => setPasswordResetUser(null)}>
          <div className="admin-modal admin-modal-sm" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2>Reset Password — {passwordResetUser.full_name}</h2>
              <button className="btn-icon" onClick={() => setPasswordResetUser(null)}><X size={20} /></button>
            </div>
            <form
              className="admin-modal-body"
              onSubmit={e => {
                e.preventDefault();
                resetPasswordMutation.mutate({ id: passwordResetUser.id, pw: newPassword });
              }}
            >
              <label>
                <span>Nova Password (mín. 12 caract.)</span>
                <input
                  required
                  type="password"
                  minLength={12}
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  placeholder="Introduza a nova password..."
                />
              </label>
              <div className="admin-modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setPasswordResetUser(null)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={resetPasswordMutation.isPending}>
                  {resetPasswordMutation.isPending ? 'A redefinir...' : 'Redefinir Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click-away to close action menus */}
      {actionMenuUser && (
        <div className="admin-menu-backdrop" onClick={() => setActionMenuUser(null)} />
      )}
    </div>
  );
}
