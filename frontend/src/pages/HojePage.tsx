/**
 * Hoje — the screen the app opens on.
 *
 * Phase 0 shows the shell: who is on duty, the sync indicator and the FAB. The
 * open serviço, the record list and the bottom sheet arrive in phase 1
 * (docs/PLANO.md §10).
 */

import { NotebookPen, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../hooks/useAuth';

export function HojePage() {
  const { user } = useAuth();

  const today = new Intl.DateTimeFormat('pt-PT', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date());

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div className="page-header-left">
          <div>
            <h1 className="page-title">Hoje</h1>
            <p className="page-subtitle">{today}</p>
          </div>
        </div>
        <span className="sync-chip sync-chip-ok">Sincronizado</span>
      </div>

      <div className="card">
        <div className="empty-state">
          <NotebookPen size={32} />
          <span className="empty-state-title">Sem serviço aberto</span>
          <p>
            {user?.nome}, abrir serviço e registar ocorrências entra na fase 1.
            Por agora isto confirma que a sessão, o desenho e a PWA funcionam no
            telemóvel.
          </p>
        </div>
      </div>

      <button
        className="fab"
        onClick={() => toast('Registos entram na fase 1')}
        aria-label="Novo registo"
      >
        <Plus size={22} />
        Registo
      </button>
    </div>
  );
}
