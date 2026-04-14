/**
 * UsersPage — Admin panel for managing application users.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MoreVertical, Search, ShieldAlert, CheckCircle, XCircle } from 'lucide-react';
import { fetchUsers } from '../api/users';
import './AdminPages.css';

export function UsersPage() {
  const [searchTerm, setSearchTerm] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['users', 'all'],
    queryFn: () => fetchUsers({ limit: 500 }),
    staleTime: 1000 * 60 * 5,
  });

  const filteredUsers = data?.users.filter(u =>
    u.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.username.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Gestão de Utilizadores</h1>
          <p className="page-subtitle">Adicione e controle os acessos dos militares.</p>
        </div>
        <button className="btn btn-primary">
          + Criar Utilizador
        </button>
      </div>

      <div className="admin-toolbar">
        <div className="search-bar">
          <Search size={18} />
          <input
            type="text"
            placeholder="Pesquisar por nome ou número..."
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
            <p>Erro ao carregar utilizadores.</p>
          </div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Username</th>
                <th>Role</th>
                <th>Estado</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td className="fw-bold">{u.full_name} <span style={{fontSize: '0.75rem', color: 'var(--text-tertiary)', marginLeft: '8px'}}>NIP {u.nip}</span></td>
                  <td>{u.username}</td>
                  <td>
                    <span className={`badge badge-${
                      u.role === 'admin' ? 'danger' :
                      u.role === 'comandante' ? 'warning' :
                      u.role === 'adjunto' ? 'primary' :
                      u.role === 'secretaria' ? 'success' :
                      'info'
                    }`}>
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
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn-icon"><MoreVertical size={18} /></button>
                  </td>
                </tr>
              ))}
              {filteredUsers.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>Sem resultados encontrados.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
