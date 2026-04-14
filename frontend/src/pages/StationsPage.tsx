/**
 * StationsPage — Admin panel for managing GNR stations.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MoreVertical, Search, ShieldAlert, CheckCircle, XCircle } from 'lucide-react';
import { fetchStations } from '../api/stations';
import './AdminPages.css';

export function StationsPage() {
  const [searchTerm, setSearchTerm] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['stations', 'all'],
    queryFn: () => fetchStations({ limit: 100 }),
    staleTime: 1000 * 60 * 10,
  });

  const filteredStations = data?.stations.filter(st =>
    st.name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">Gestão de Postos</h1>
          <p className="page-subtitle">Controle as esquadras e agrupamentos.</p>
        </div>
        <button className="btn btn-primary">
          + Criar Posto
        </button>
      </div>

      <div className="admin-toolbar">
        <div className="search-bar">
          <Search size={18} />
          <input
            type="text"
            placeholder="Pesquisar por nome do posto..."
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
          <table className="admin-table">
            <thead>
              <tr>
                <th>Nome da Infraestrutura</th>
                <th>Morada</th>
                <th>Lotação Máx.</th>
                <th>Estado</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {filteredStations.map((st) => (
                <tr key={st.id}>
                  <td className="fw-bold">{st.name}</td>
                  <td className="text-muted">{st.address || '-'}</td>
                  <td>{/* 'max_capacity' not modeled in the current Station type */}</td>
                  <td>
                    {st.is_active ? (
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
              {filteredStations.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>Sem postos encontrados.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
