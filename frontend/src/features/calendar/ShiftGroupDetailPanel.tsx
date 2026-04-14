/**
 * ShiftGroupDetailPanel — slide-in panel showing all members of a grouped shift / patrol.
 * Allows military to propose a swap with any colleague in the patrol.
 */

import { useState } from 'react';
import {
  X,
  CalendarDays,
  Clock,
  Tag,
  Users,
  ArrowLeftRight,
  Trash2,
  AlertTriangle,
} from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { pt } from 'date-fns/locale';
import type { AuthUser, Shift } from '../../types';
import { getInitials } from '../../utils/helpers';
import { SwapRequestModal } from '../swaps/SwapRequestModal';
import './ShiftGroupDetailPanel.css';

interface ShiftGroupDetailPanelProps {
  shifts: Shift[];
  onClose: () => void;
  currentUser: AuthUser | null;
  /** If true, show edit controls per shift */
  canEdit?: boolean;
  onEditShift?: (shift: Shift) => void;
  onDeleteShift?: (shift: Shift) => void;
}

function fmtDate(d: string) {
  try {
    const p = parseISO(d);
    return isValid(p) ? format(p, "EEEE, d 'de' MMMM 'de' yyyy", { locale: pt }) : d;
  } catch { return d; }
}

function fmtTime(dt: string | null) {
  if (!dt) return '—';
  // Take HH:MM from ISO string (strip TZ)
  const clean = dt.replace(/([+-]\d{2}:\d{2}|Z)$/, '');
  const t = clean.substring(11, 16);
  return t || '—';
}

export function ShiftGroupDetailPanel({
  shifts,
  onClose,
  currentUser,
  canEdit = false,
  onEditShift,
  onDeleteShift,
}: ShiftGroupDetailPanelProps) {
  const [swapTargetShift, setSwapTargetShift] = useState<Shift | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);

  if (!shifts.length) return null;

  // Use first shift for type/time info (all same type + same day)
  const sample = shifts[0]!;
  const isMilitar = currentUser?.role === 'militar';

  // Check if current user is IN this patrol
  const myShiftInGroup = shifts.find((s) => s.user_id === currentUser?.id);

  const sDate = sample.date;
  const sTime = fmtTime(sample.start_datetime);
  const eTime = fmtTime(sample.end_datetime);
  const isAllDay = sTime === '00:00' && eTime === '00:00';

  return (
    <>
      <div className="modal-overlay" onClick={onClose} />
      <div className="sgdp-panel animate-slide-in">
        {/* Header */}
        <div className="sgdp-header">
          <div className="sgdp-header-left">
            <h2 className="sgdp-title">
              {sample.shift_type_name ?? 'Turno'}
            </h2>
            <span className="sgdp-member-pill">
              <Users size={12} />
              {shifts.length} militar{shifts.length !== 1 ? 'es' : ''}
            </span>
          </div>
          <button className="btn-icon" onClick={onClose} title="Fechar">
            <X size={20} />
          </button>
        </div>

        {/* Color bar */}
        <div
          className="sgdp-color-bar"
          style={{ backgroundColor: sample.shift_type_color ?? 'var(--color-primary-500)' }}
        />

        {/* Meta */}
        <div className="sgdp-meta">
          <div className="sgdp-meta-item">
            <CalendarDays size={15} />
            <span>{fmtDate(sDate)}</span>
          </div>
          {!isAllDay && (
            <div className="sgdp-meta-item">
              <Clock size={15} />
              <span>{sTime} — {eTime}</span>
            </div>
          )}
          {sample.shift_type_code && (
            <div className="sgdp-meta-item">
              <Tag size={15} />
              <span className="sgdp-type-code">{sample.shift_type_code}</span>
            </div>
          )}
        </div>

        {/* Members list */}
        <div className="sgdp-section-label">Militares na patrulha</div>
        <div className="sgdp-members">
          {shifts.map((s) => {
            const isMe = s.user_id === currentUser?.id;
            const name = s.user_name ?? 'Militar';
            const initials = getInitials(name);
            // A military can propose a swap if:
            //  - they're in the patrol (myShiftInGroup exists)
            //  - OR they are not in the patrol but want to swap into it (offer one of their own shifts)
            // For simplicity: any military can click "Pedir Troca" on a non-self entry
            const showSwapBtn = isMilitar && !isMe && s.status === 'published';

            return (
              <div key={s.id} className={`sgdp-member-row ${isMe ? 'sgdp-member-me' : ''}`}>
                <div
                  className="sgdp-avatar"
                  style={{ background: sample.shift_type_color ?? 'var(--color-primary-600)' }}
                >
                  {initials}
                </div>
                <div className="sgdp-member-info">
                  <span className="sgdp-member-name">{name}</span>
                  {s.user_numero_ordem && (
                    <span className="sgdp-member-ordem" title="N.º de Ordem">#{s.user_numero_ordem}</span>
                  )}
                  {isMe && <span className="sgdp-me-badge">Você</span>}
                </div>
                <div className="sgdp-member-actions">
                  {showSwapBtn && (
                    <button
                      className="btn btn-ghost btn-sm sgdp-swap-btn"
                      title={`Propor troca com ${name}`}
                      onClick={() => setSwapTargetShift(s)}
                    >
                      <ArrowLeftRight size={13} />
                      Pedir Troca
                    </button>
                  )}
                  {canEdit && onEditShift && (
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => onEditShift(s)}
                    >
                      Editar
                    </button>
                  )}
                  {canEdit && onDeleteShift && confirmDeleteId !== s.id && (
                    <button
                      className="btn btn-ghost btn-sm sgdp-remove-btn"
                      title={`Remover ${name}`}
                      onClick={() => setConfirmDeleteId(s.id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
                {/* Inline confirm for this member */}
                {canEdit && onDeleteShift && confirmDeleteId === s.id && (
                  <div className="sgdp-confirm-inline">
                    <AlertTriangle size={14} />
                    <span>Remover {name.split(' ').slice(-1)[0]}?</span>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => { onDeleteShift(s); setConfirmDeleteId(null); }}
                    >
                      Confirmar
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      Cancelar
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Remove All Confirmation */}
        {confirmDeleteAll && canEdit && onDeleteShift && (
          <div className="sgdp-delete-all-confirm">
            <div className="sgdp-delete-all-header">
              <AlertTriangle size={16} />
              <strong>Remover todos os {shifts.length} militares?</strong>
            </div>
            <p className="sgdp-delete-all-text">
              {shifts.some(s => s.status === 'published')
                ? 'Os militares com turnos publicados serão notificados.'
                : 'Todos os rascunhos serão removidos.'}
            </p>
            <div className="sgdp-delete-all-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDeleteAll(false)}>
                Cancelar
              </button>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => {
                  shifts.forEach(s => onDeleteShift(s));
                  setConfirmDeleteAll(false);
                  onClose();
                }}
              >
                <Trash2 size={13} />
                Confirmar Remoção
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="sgdp-footer">
          {canEdit && onDeleteShift && shifts.length > 1 && !confirmDeleteAll && (
            <button
              className="btn btn-ghost btn-sm sgdp-remove-all-btn"
              onClick={() => setConfirmDeleteAll(true)}
            >
              <Trash2 size={14} />
              Remover Todos
            </button>
          )}
          {myShiftInGroup && isMilitar && (
            <span className="sgdp-my-shift-note">
              Você faz parte desta patrulha
            </span>
          )}
          <button className="btn btn-secondary" onClick={onClose} style={{ marginLeft: 'auto' }}>
            Fechar
          </button>
        </div>
      </div>

      {/* Swap modal — targetShift preset, user picks which of their own shifts to offer */}
      {swapTargetShift && (
        <SwapRequestModal
          targetShift={swapTargetShift}
          onClose={() => setSwapTargetShift(null)}
        />
      )}
    </>
  );
}
