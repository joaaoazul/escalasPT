/**
 * PublishActionToolbar — bottom floating toolbar for Commander
 * Appears when there are draft shifts in the current view.
 */

import { Send } from 'lucide-react';
import { useShiftMutations } from '../../hooks/useShiftMutations';
import type { Shift } from '../../types';
import './PublishActionToolbar.css';

interface PublishActionToolbarProps {
  shifts: Shift[];
}

export function PublishActionToolbar({ shifts }: PublishActionToolbarProps) {
  const { publishShifts } = useShiftMutations();

  const draftShifts = shifts.filter((s) => s.status === 'draft');
  const draftCount = draftShifts.length;

  if (draftCount === 0) return null;

  const handlePublish = () => {
    const shiftIds = draftShifts.map((s) => s.id);
    publishShifts.mutate(shiftIds);
  };

  return (
    <div className="publish-toolbar animate-slide-up">
      <div className="publish-toolbar-content">
        <div className="publish-toolbar-info">
          <div className="publish-icon" />
          <span className="publish-title">Rascunho não publicado</span>
          <span className="publish-desc">
            — <strong>{draftCount}</strong> turno{draftCount !== 1 ? 's' : ''} oculto{draftCount !== 1 ? 's' : ''} dos militares
          </span>
        </div>
        <div className="publish-toolbar-actions">
          <button
            className="btn btn-sm btn-primary"
            onClick={handlePublish}
            disabled={publishShifts.isPending}
          >
            {publishShifts.isPending ? (
              <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
            ) : (
              <>
                <Send size={13} />
                Publicar
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
