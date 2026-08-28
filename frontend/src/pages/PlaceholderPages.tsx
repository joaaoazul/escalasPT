/**
 * Screens whose content lands in later phases. They exist now so the
 * navigation, the layout and the route guards are real from day one.
 */

import { BarChart3, ClipboardList, NotebookPen, Settings } from 'lucide-react';
import type { ReactNode } from 'react';

function Placeholder({
  title,
  phase,
  icon,
  children,
}: {
  title: string;
  phase: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div className="page-header-left">
          <div>
            <h1 className="page-title">{title}</h1>
            <p className="page-subtitle">{phase}</p>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="empty-state">
          {icon}
          <span className="empty-state-title">{title}</span>
          <p>{children}</p>
        </div>
      </div>
    </div>
  );
}

export function ServicosPage() {
  return (
    <Placeholder title="Serviços" phase="Fase 1" icon={<ClipboardList size={32} />}>
      Histórico de turnos, com o PDF de cada um.
    </Placeholder>
  );
}

export function RegistosPage() {
  return (
    <Placeholder title="Registos" phase="Fase 1" icon={<NotebookPen size={32} />}>
      Ocorrências, fiscalizações e notas, com fotos e localização.
    </Placeholder>
  );
}

export function PainelPage() {
  return (
    <Placeholder title="Painel" phase="Fase 3" icon={<BarChart3 size={32} />}>
      Contagens por tipo, zona e hora, e o mapa de pontos quentes.
    </Placeholder>
  );
}

export function AdminPage() {
  return (
    <Placeholder title="Administração" phase="Fase 4" icon={<Settings size={32} />}>
      Utilizadores, catálogos, modelos de texto, auditoria e fila de conservação.
    </Placeholder>
  );
}
