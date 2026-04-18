/**
 * ShiftDetailModal — displays full shift details on event click.
 */

import { useState } from 'react';
import { X, Clock, User, Users, MapPin, FileText, Tag, CalendarDays, ArrowLeftRight, AlertTriangle, Trash2 } from 'lucide-react';
import type { Shift } from '../../types';
import { formatDate, formatTime, formatStatus, getStatusBadgeClass } from '../../utils/helpers';
import { SwapRequestModal } from '../swaps/SwapRequestModal';
import './ShiftDetailModal.css';

interface ShiftDetailModalProps {
  shift: Shift | null;
  onClose: () => void;
  canEdit?: boolean;
  onEdit?: (shift: Shift) => void;
  onDelete?: (shift: Shift) => void;
  /** Sibling shifts in the same service group (same type+date+time+grat_type+location) */
  siblingShifts?: Shift[];
  /** Delete all shifts in the group */
  onDeleteGroup?: (shifts: Shift[]) => void;
  /** When set, shows the "Pedir Troca" button for this military's own published shifts */
  canRequestSwap?: boolean;
}

export function ShiftDetailModal({
  shift,
  onClose,
  canEdit = false,
  onEdit,
  onDelete,
  siblingShifts = [],
  onDeleteGroup,
  canRequestSwap = false,
}: ShiftDetailModalProps) {
  const [showSwapModal, setShowSwapModal] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<'single' | 'group' | false>(false);
  if (!shift) return null;

  const isPublished = shift.status === 'published';
  const hasGroup = siblingShifts.length > 1;
  const allShiftsInGroup = siblingShifts.length > 0 ? siblingShifts : [shift];

  const handleDeleteClick = () => {
    if (confirmDelete === 'single') {
      onDelete?.(shift);
      setConfirmDelete(false);
    } else {
      setConfirmDelete('single');
    }
  };

  const handleDeleteGroupClick = () => {
    if (confirmDelete === 'group') {
      onDeleteGroup?.(allShiftsInGroup);
      setConfirmDelete(false);
    } else {
      setConfirmDelete('group');
    }
  };

  return (
    <>
      <div className="modal-overlay" onClick={onClose} />
      <div className="shift-detail-panel animate-slide-in">
        {/* Header */}
        <div className="sdp-header">
          <div className="sdp-header-info">
            <h2 className="sdp-title">
              {shift.shift_type_name ?? 'Turno'}
            </h2>
            <span className={`badge ${getStatusBadgeClass(shift.status)}`}>
              {formatStatus(shift.status)}
            </span>
          </div>
          <button className="btn-icon" onClick={onClose} title="Fechar">
            <X size={20} />
          </button>
        </div>

        {/* Color indicator */}
        <div
          className="sdp-color-bar"
          style={{ backgroundColor: shift.shift_type_color ?? 'var(--color-primary-500)' }}
        />

        {/* Details */}
        <div className="sdp-body">
          <div className="sdp-field">
            <div className="sdp-field-icon">
              <CalendarDays size={16} />
            </div>
            <div className="sdp-field-content">
              <span className="sdp-field-label">Data</span>
              <span className="sdp-field-value">
                {formatDate(shift.date, "EEEE, dd 'de' MMMM 'de' yyyy")}
              </span>
            </div>
          </div>

          <div className="sdp-field">
            <div className="sdp-field-icon">
              <Clock size={16} />
            </div>
            <div className="sdp-field-content">
              <span className="sdp-field-label">Horário</span>
              <span className="sdp-field-value">
                {formatTime(shift.start_datetime)} — {formatTime(shift.end_datetime)}
              </span>
            </div>
          </div>

          {shift.user_name && (
            <div className="sdp-field">
              <div className="sdp-field-icon">
                <User size={16} />
              </div>
              <div className="sdp-field-content">
                <span className="sdp-field-label">Militar</span>
                <span className="sdp-field-value">{shift.user_name}</span>
              </div>
            </div>
          )}

          {shift.shift_type_code && (
            <div className="sdp-field">
              <div className="sdp-field-icon">
                <Tag size={16} />
              </div>
              <div className="sdp-field-content">
                <span className="sdp-field-label">Tipo de Turno</span>
                <span className="sdp-field-value">
                  <span
                    className="sdp-type-dot"
                    style={{ backgroundColor: shift.shift_type_color ?? undefined }}
                  />
                  {shift.shift_type_name} ({shift.shift_type_code})
                </span>
              </div>
            </div>
          )}

          {shift.notes && (
            <div className="sdp-field sdp-notes-field">
              <div className="sdp-field-icon">
                <FileText size={16} />
              </div>
              <div className="sdp-field-content">
                <span className="sdp-field-label">Notas / Indicações</span>
                <div className="sdp-notes-content">{shift.notes}</div>
              </div>
            </div>
          )}

          {shift.published_at && (
            <div className="sdp-field">
              <div className="sdp-field-icon">
                <MapPin size={16} />
              </div>
              <div className="sdp-field-content">
                <span className="sdp-field-label">Publicado em</span>
                <span className="sdp-field-value">
                  {formatDate(shift.published_at, "dd/MM/yyyy 'às' HH:mm")}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Group members */}
        {hasGroup && (
          <div className="sdp-group">
            <div className="sdp-group-header">
              <Users size={14} />
              <span>Militares neste serviço ({allShiftsInGroup.length})</span>
            </div>
            <div className="sdp-group-list">
              {allShiftsInGroup.map((s) => (
                <div
                  key={s.id}
                  className={`sdp-group-member${s.id === shift.id ? ' sdp-group-member--active' : ''}`}
                >
                  <span
                    className="sdp-type-dot"
                    style={{ backgroundColor: s.shift_type_color ?? 'var(--color-primary-500)' }}
                  />
                  <span className="sdp-group-member-num">{s.user_numero_ordem ?? '—'}</span>
                  <span className="sdp-group-member-name">{s.user_name ?? '?'}</span>
                  {s.id === shift.id && <span className="sdp-group-member-you">selecionado</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Delete Confirmation Banner */}
        {confirmDelete && (
          <div className="sdp-delete-confirm">
            <div className="sdp-delete-confirm-header">
              <AlertTriangle size={18} />
              <strong>
                {confirmDelete === 'group'
                  ? `Remover ${allShiftsInGroup.length} turno(s) deste serviço`
                  : isPublished ? 'Cancelar turno publicado' : 'Remover rascunho'}
              </strong>
            </div>
            <div className="sdp-delete-confirm-details">
              {confirmDelete === 'single' && shift.user_name && (
                <span><User size={14} /> {shift.user_name}</span>
              )}
              {confirmDelete === 'group' && (
                <span><Users size={14} /> {allShiftsInGroup.map(s => s.user_name).filter(Boolean).join(', ')}</span>
              )}
              <span><Tag size={14} /> {shift.shift_type_name} ({shift.shift_type_code})</span>
              <span><CalendarDays size={14} /> {formatDate(shift.date, "dd/MM/yyyy")}</span>
              <span><Clock size={14} /> {formatTime(shift.start_datetime)} — {formatTime(shift.end_datetime)}</span>
            </div>
            {isPublished && (
              <p className="sdp-delete-warning">
                {confirmDelete === 'group' ? 'Os militares serão notificados do cancelamento.' : 'O militar será notificado do cancelamento.'}
              </p>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="sdp-footer">
          {canEdit && !confirmDelete && (
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginRight: 'auto', flexWrap: 'wrap' }}>
              <button
                className="btn btn-secondary"
                onClick={() => onEdit?.(shift)}
              >
                Editar
              </button>
              <button
                className="btn btn-ghost sdp-btn-remove"
                onClick={handleDeleteClick}
              >
                <Trash2 size={15} />
                Remover
              </button>
              {hasGroup && onDeleteGroup && (
                <button
                  className="btn btn-ghost sdp-btn-remove-group"
                  onClick={handleDeleteGroupClick}
                >
                  <Trash2 size={15} />
                  Remover serviço ({allShiftsInGroup.length})
                </button>
              )}
            </div>
          )}
          {canEdit && confirmDelete && (
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginRight: 'auto', width: '100%' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setConfirmDelete(false)}
              >
                Cancelar
              </button>
              <button
                className="btn btn-danger"
                onClick={confirmDelete === 'group' ? handleDeleteGroupClick : handleDeleteClick}
              >
                <Trash2 size={15} />
                {confirmDelete === 'group'
                  ? `Confirmar (${allShiftsInGroup.length} turnos)`
                  : isPublished ? 'Confirmar Cancelamento' : 'Confirmar Remoção'}
              </button>
            </div>
          )}
          {canRequestSwap && shift.status === 'published' && (
            <button
              className="btn btn-secondary"
              style={{ marginRight: 'auto' }}
              onClick={() => setShowSwapModal(true)}
            >
              <ArrowLeftRight size={15} />
              Pedir Troca
            </button>
          )}
          <button className="btn btn-secondary" onClick={onClose} style={{ marginLeft: 'auto' }}>
            Fechar
          </button>
        </div>
      </div>

      {showSwapModal && (
        <SwapRequestModal
          myShift={shift}
          onClose={() => setShowSwapModal(false)}
        />
      )}
    </>
  );
}
