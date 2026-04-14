/**
 * AdminStationsPage — Full CRUD station management with create/edit modals.
 */

import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search, ShieldAlert, CheckCircle, XCircle, Plus,
  Edit, X, ChevronLeft, ChevronRight, Users, Building2, Rocket,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchStations, createStation, updateStation,
  type StationCreateData, type StationUpdateData,
} from '../api/stations';
import { fetchUsers } from '../api/users';
import { onboardStation, type StationOnboardRequest } from '../api/admin';
import type { Station } from '../types';
import './AdminPages.css';

export function AdminStationsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showOnboardModal, setShowOnboardModal] = useState(false);
  const [editingStation, setEditingStation] = useState<Station | null>(null);
  const [createForm, setCreateForm] = useState<StationCreateData>({ name: '', phone: '', address: '' });
  const [editForm, setEditForm] = useState<StationUpdateData>({});
  const [onboardForm, setOnboardForm] = useState<StationOnboardRequest>({
    station_name: '', station_code: '', station_address: '', station_phone: '',
    comandante_username: '', comandante_email: '', comandante_password: '',
    comandante_full_name: '', comandante_nip: '', comandante_phone: '',
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-stations', page],
    queryFn: () => fetchStations({ skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
    staleTime: 1000 * 60,
  });

  const { data: usersData } = useQuery({
    queryKey: ['admin-users-count'],
    queryFn: () => fetchUsers({ limit: 500 }),
    staleTime: 1000 * 60 * 5,
  });

  const userCountByStation = useMemo(() => {
    const map: Record<string, number> = {};
    usersData?.users.forEach(u => {
      if (u.station_id) {
        map[u.station_id] = (map[u.station_id] || 0) + 1;
      }
    });
    return map;
  }, [usersData]);

  const filteredStations = data?.stations.filter(st =>
    st.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    st.code.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE);

  const createMutation = useMutation({
    mutationFn: (d: StationCreateData) => createStation(d),
    onSuccess: () => {
      toast.success('Posto criado com sucesso');
      queryClient.invalidateQueries({ queryKey: ['admin-stations'] });
      setShowCreateModal(false);
      setCreateForm({ name: '', phone: '', address: '' });
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Erro ao criar posto'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, d }: { id: string; d: StationUpdateData }) => updateStation(id, d),
    onSuccess: () => {
      toast.success('Posto atualizado');
      queryClient.invalidateQueries({ queryKey: ['admin-stations'] });
      setEditingStation(null);
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Erro ao atualizar'),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      updateStation(id, { is_active: active }),
    onSuccess: (_, { active }) => {
      toast.success(active ? 'Posto ativado' : 'Posto desativado');
      queryClient.invalidateQueries({ queryKey: ['admin-stations'] });
    },
  });

  const onboardMutation = useMutation({
    mutationFn: (d: StationOnboardRequest) => onboardStation(d),
    onSuccess: (res) => {
      toast.success(`Posto "${res.station_name}" criado com Comandante ${res.comandante_username}`);
      queryClient.invalidateQueries({ queryKey: ['admin-stations'] });
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setShowOnboardModal(false);
      setOnboardForm({
        station_name: '', station_code: '', station_address: '', station_phone: '',
        comandante_username: '', comandante_email: '', comandante_password: '',
        comandante_full_name: '', comandante_nip: '', comandante_phone: '',
      });
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || 'Erro ao provisionar posto'),
  });

  const openEdit = (st: Station) => {
    setEditForm({ name: st.name, address: st.address || '', phone: st.phone || '', is_active: st.is_active });
    setEditingStation(st);
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Gestão de Postos</h1>
          <p className="page-subtitle">{data?.total || 0} postos registados.</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button className="btn btn-primary" onClick={() => setShowOnboardModal(true)}>
            <Rocket size={16} /> Provisionar Posto
          </button>
          <button className="btn btn-ghost" onClick={() => setShowCreateModal(true)}>
            <Plus size={16} /> Criar Posto
          </button>
        </div>
      </div>

      <div className="admin-toolbar">
        <div className="search-bar">
          <Search size={18} />
          <input
            type="text"
            placeholder="Pesquisar por nome ou código..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <div className="admin-table-container">
        {isLoading ? (
          <div className="page-loader"><div className="spinner" /></div>
        ) : error ? (
          <div className="empty-state">
            <ShieldAlert size={40} className="text-danger" />
            <p>Erro ao carregar postos.</p>
          </div>
        ) : (
          <>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Código</th>
                  <th>Morada</th>
                  <th>Telefone</th>
                  <th>Efetivo</th>
                  <th>Estado</th>
                  <th style={{ textAlign: 'right' }}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {filteredStations.map(st => (
                  <tr key={st.id}>
                    <td className="fw-bold">
                      <Building2 size={14} style={{ marginRight: 6, opacity: 0.5 }} />
                      {st.name}
                    </td>
                    <td><span className="badge badge-info">{st.code}</span></td>
                    <td className="text-muted">{st.address || '—'}</td>
                    <td className="text-muted">{st.phone || '—'}</td>
                    <td>
                      <span className="state-badge" style={{ color: 'var(--color-info-400)' }}>
                        <Users size={14} /> {userCountByStation[st.id] || 0}
                      </span>
                    </td>
                    <td>
                      {st.is_active ? (
                        <span className="state-badge text-success"><CheckCircle size={14} /> Ativo</span>
                      ) : (
                        <span className="state-badge text-danger"><XCircle size={14} /> Inativo</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button className="btn-icon" onClick={() => openEdit(st)} title="Editar">
                        <Edit size={16} />
                      </button>
                      <button
                        className="btn-icon"
                        onClick={() => toggleActiveMutation.mutate({ id: st.id, active: !st.is_active })}
                        title={st.is_active ? 'Desativar' : 'Ativar'}
                      >
                        {st.is_active ? <XCircle size={16} /> : <CheckCircle size={16} />}
                      </button>
                    </td>
                  </tr>
                ))}
                {filteredStations.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                      Sem postos encontrados.
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

      {/* Create Modal */}
      {showCreateModal && (
        <div className="admin-modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="admin-modal" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2>Criar Posto</h2>
              <button className="btn-icon" onClick={() => setShowCreateModal(false)}><X size={20} /></button>
            </div>
            <form
              className="admin-modal-body"
              onSubmit={e => { e.preventDefault(); createMutation.mutate(createForm); }}
            >
              <div className="admin-form-grid">
                <label>
                  <span>Nome do Posto *</span>
                  <input
                    required
                    value={createForm.name}
                    onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="Ex: Posto Territorial de Sintra"
                  />
                </label>
                <label>
                  <span>Código *</span>
                  <input
                    required
                    value={(createForm as any).code || ''}
                    onChange={e => setCreateForm(f => ({ ...f, code: e.target.value } as any))}
                    placeholder="Ex: PT-SINTRA"
                  />
                </label>
                <label>
                  <span>Morada</span>
                  <input
                    value={createForm.address || ''}
                    onChange={e => setCreateForm(f => ({ ...f, address: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Telefone</span>
                  <input
                    value={createForm.phone || ''}
                    onChange={e => setCreateForm(f => ({ ...f, phone: e.target.value }))}
                  />
                </label>
              </div>
              <div className="admin-modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'A criar...' : 'Criar Posto'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingStation && (
        <div className="admin-modal-overlay" onClick={() => setEditingStation(null)}>
          <div className="admin-modal" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2>Editar — {editingStation.name}</h2>
              <button className="btn-icon" onClick={() => setEditingStation(null)}><X size={20} /></button>
            </div>
            <form
              className="admin-modal-body"
              onSubmit={e => { e.preventDefault(); updateMutation.mutate({ id: editingStation.id, d: editForm }); }}
            >
              <div className="admin-form-grid">
                <label>
                  <span>Nome</span>
                  <input
                    value={editForm.name || ''}
                    onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Morada</span>
                  <input
                    value={editForm.address || ''}
                    onChange={e => setEditForm(f => ({ ...f, address: e.target.value }))}
                  />
                </label>
                <label>
                  <span>Telefone</span>
                  <input
                    value={editForm.phone || ''}
                    onChange={e => setEditForm(f => ({ ...f, phone: e.target.value }))}
                  />
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
                <button type="button" className="btn btn-ghost" onClick={() => setEditingStation(null)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? 'A guardar...' : 'Guardar Alterações'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Onboard Station Modal */}
      {showOnboardModal && (
        <div className="admin-modal-overlay" onClick={() => setShowOnboardModal(false)}>
          <div className="admin-modal admin-modal--wide" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2><Rocket size={20} /> Provisionar Novo Posto</h2>
              <button className="btn-icon" onClick={() => setShowOnboardModal(false)}><X size={20} /></button>
            </div>
            <form
              className="admin-modal-body"
              onSubmit={e => { e.preventDefault(); onboardMutation.mutate(onboardForm); }}
            >
              <h3 style={{ margin: '0 0 var(--space-3)', fontSize: '0.95rem', color: 'var(--color-primary-300)' }}>
                <Building2 size={16} /> Dados do Posto
              </h3>
              <div className="admin-form-grid">
                <label>
                  <span>Nome do Posto *</span>
                  <input required value={onboardForm.station_name}
                    onChange={e => setOnboardForm(f => ({ ...f, station_name: e.target.value }))}
                    placeholder="Ex: Posto Territorial de Sintra" />
                </label>
                <label>
                  <span>Código *</span>
                  <input required value={onboardForm.station_code}
                    onChange={e => setOnboardForm(f => ({ ...f, station_code: e.target.value }))}
                    placeholder="Ex: PT-SINTRA" />
                </label>
                <label>
                  <span>Morada</span>
                  <input value={onboardForm.station_address || ''}
                    onChange={e => setOnboardForm(f => ({ ...f, station_address: e.target.value }))} />
                </label>
                <label>
                  <span>Telefone</span>
                  <input value={onboardForm.station_phone || ''}
                    onChange={e => setOnboardForm(f => ({ ...f, station_phone: e.target.value }))} />
                </label>
              </div>

              <h3 style={{ margin: 'var(--space-5) 0 var(--space-3)', fontSize: '0.95rem', color: 'var(--color-primary-300)' }}>
                <Users size={16} /> Comandante
              </h3>
              <div className="admin-form-grid">
                <label>
                  <span>Nome Completo *</span>
                  <input required value={onboardForm.comandante_full_name}
                    onChange={e => setOnboardForm(f => ({ ...f, comandante_full_name: e.target.value }))} />
                </label>
                <label>
                  <span>NIP *</span>
                  <input required value={onboardForm.comandante_nip}
                    onChange={e => setOnboardForm(f => ({ ...f, comandante_nip: e.target.value }))}
                    placeholder="Ex: 12345678" />
                </label>
                <label>
                  <span>Username *</span>
                  <input required value={onboardForm.comandante_username}
                    onChange={e => setOnboardForm(f => ({ ...f, comandante_username: e.target.value }))} />
                </label>
                <label>
                  <span>Email *</span>
                  <input required type="email" value={onboardForm.comandante_email}
                    onChange={e => setOnboardForm(f => ({ ...f, comandante_email: e.target.value }))} />
                </label>
                <label>
                  <span>Password *</span>
                  <input required type="password" minLength={12} value={onboardForm.comandante_password}
                    onChange={e => setOnboardForm(f => ({ ...f, comandante_password: e.target.value }))}
                    placeholder="Mínimo 12 caracteres" />
                </label>
                <label>
                  <span>Telefone</span>
                  <input value={onboardForm.comandante_phone || ''}
                    onChange={e => setOnboardForm(f => ({ ...f, comandante_phone: e.target.value }))} />
                </label>
              </div>

              <div className="admin-modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowOnboardModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={onboardMutation.isPending}>
                  {onboardMutation.isPending ? 'A provisionar...' : 'Provisionar Posto'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
