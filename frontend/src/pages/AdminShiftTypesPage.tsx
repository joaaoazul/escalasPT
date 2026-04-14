/**
 * AdminShiftTypesPage — View and manage shift types across all stations.
 */

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, ShieldAlert, Clock, Users } from 'lucide-react';
import { fetchShiftTypes } from '../api/shiftTypes';
import { fetchStations } from '../api/stations';
import './AdminPages.css';

export function AdminShiftTypesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [stationFilter, setStationFilter] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-shift-types'],
    queryFn: () => fetchShiftTypes(),
    staleTime: 1000 * 60 * 5,
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

  const filteredTypes = (data?.shift_types || []).filter(st => {
    const matchSearch = st.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      st.code.toLowerCase().includes(searchTerm.toLowerCase());
    const matchStation = !stationFilter || st.station_id === stationFilter;
    return matchSearch && matchStation;
  });

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Tipos de Turno</h1>
          <p className="page-subtitle">Todos os tipos de turno configurados no sistema.</p>
        </div>
      </div>

      <div className="admin-toolbar">
        <div className="search-bar">
          <Search size={18} />
          <input
            type="text"
            placeholder="Pesquisar por nome ou código..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="admin-filters">
          <select value={stationFilter} onChange={e => setStationFilter(e.target.value)}>
            <option value="">Todos os postos</option>
            {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      <div className="admin-table-container">
        {isLoading ? (
          <div className="page-loader"><div className="spinner" /></div>
        ) : error ? (
          <div className="empty-state">
            <ShieldAlert size={40} className="text-danger" />
            <p>Erro ao carregar tipos de turno.</p>
          </div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Cor</th>
                <th>Nome</th>
                <th>Código</th>
                <th>Posto</th>
                <th>Horário</th>
                <th>Mín. Efetivo</th>
                <th>Ausência</th>
                <th>Slots Fixos</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {filteredTypes.map(st => (
                <tr key={st.id}>
                  <td>
                    <div
                      className="admin-color-swatch"
                      style={{ background: st.color }}
                      title={st.color}
                    />
                  </td>
                  <td className="fw-bold">{st.name}</td>
                  <td><span className="badge badge-info">{st.code}</span></td>
                  <td className="text-muted">{stationMap[st.station_id] || '—'}</td>
                  <td>
                    <span className="state-badge" style={{ color: 'var(--text-secondary)' }}>
                      <Clock size={14} /> {st.start_time} – {st.end_time}
                    </span>
                  </td>
                  <td>
                    <span className="state-badge" style={{ color: 'var(--color-info-400)' }}>
                      <Users size={14} /> {st.min_staff}
                    </span>
                  </td>
                  <td>{st.is_absence ? <span className="badge badge-warning">Sim</span> : '—'}</td>
                  <td>{st.fixed_slots ? <span className="badge badge-primary">Sim</span> : '—'}</td>
                  <td>
                    {st.is_active ? (
                      <span className="state-badge text-success">Ativo</span>
                    ) : (
                      <span className="state-badge text-danger">Inativo</span>
                    )}
                  </td>
                </tr>
              ))}
              {filteredTypes.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                    Sem tipos de turno encontrados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
