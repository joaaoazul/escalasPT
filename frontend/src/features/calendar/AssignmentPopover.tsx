/**
 * AssignmentPopover — appears after dragging a shift type onto the calendar.
 * Lets the comandante/adjunto pick one or more militares.
 * For fixed-slot types the hours are pre-set; for GRAT/absences the user enters them.
 */

import { useState, useEffect, useRef, type FormEvent } from 'react';
import { X, Check, Clock, MapPin, FileText, Tag } from 'lucide-react';
import { format, parseISO, addDays } from 'date-fns';
import { useStationUsers } from '../../hooks/useStationUsers';
import { useShiftTypes } from '../../hooks/useShiftTypes';
import type { Shift } from '../../types';
import './AssignmentPopover.css';

/** Shift type codes that are absences / GRAT (not normal services) */
const _NON_SERVICE_CODES = new Set(['CONV', 'DIL', 'F', 'FER', 'LIC', 'MF', 'INST', 'T', 'GRAT']);

export interface AssignmentPayload {
  shiftTypeId: string;
  userIds: string[];
  startDatetime: string;
  endDatetime: string;
  notes?: string;
  location?: string;
  grat_type?: string;
}

interface AssignmentPopoverProps {
  shiftTypeId: string;
  date: Date;
  /** Viewport position of the drop (to anchor the popover) */
  position: { x: number; y: number };
  onConfirm: (payload: AssignmentPayload) => void;
  onClose: () => void;
  isPending?: boolean;
  /** Existing shifts for the selected day — used to hide already-assigned militares */
  existingShifts?: Shift[];
}

export function AssignmentPopover({
  shiftTypeId,
  date,
  position,
  onConfirm,
  onClose,
  isPending = false,
  existingShifts = [],
}: AssignmentPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const { data: users = [] } = useStationUsers();
  const { data: shiftTypes = [] } = useShiftTypes();

  const shiftType = shiftTypes.find((st) => st.id === shiftTypeId);
  const dateStr = format(date, 'yyyy-MM-dd');

  // Compute default start/end from shift type
  const defaultStart = shiftType?.fixed_slots
    ? shiftType.start_time.substring(0, 5)
    : shiftType?.is_absence
      ? '00:00'
      : '08:00';

  const defaultEnd = shiftType?.fixed_slots
    ? shiftType.end_time.substring(0, 5)
    : shiftType?.is_absence
      ? '00:00'
      : '16:00';

  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [startTime, setStartTime] = useState(defaultStart);
  const [endTime, setEndTime] = useState(defaultEnd);
  const [notes, setNotes] = useState('');
  const [location, setLocation] = useState('');
  const [gratType, setGratType] = useState('');
  const [hasAutoSelected, setHasAutoSelected] = useState(false);

  // Auto-select users with a fixed assignment matching this shift type
  useEffect(() => {
    if (hasAutoSelected || users.length === 0) return;
    const fixedIds = users
      .filter((u) => u.default_shift_type_id === shiftTypeId)
      .map((u) => u.id);
    if (fixedIds.length > 0) {
      setSelectedUserIds(fixedIds);
    }
    setHasAutoSelected(true);
  }, [users, shiftTypeId, hasAutoSelected]);

  // Re-apply defaults when shiftType loads
  useEffect(() => {
    if (!shiftType) return;
    setStartTime(shiftType.fixed_slots ? shiftType.start_time.substring(0, 5) : shiftType.is_absence ? '00:00' : '08:00');
    setEndTime(shiftType.fixed_slots ? shiftType.end_time.substring(0, 5) : shiftType.is_absence ? '00:00' : '16:00');
  }, [shiftType]);

  // Clamp popover to viewport
  useEffect(() => {
    const el = popoverRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const right = position.x + rect.width;
    const bottom = position.y + rect.height;
    let left = position.x;
    let top = position.y;
    if (right > window.innerWidth - 16) left = window.innerWidth - rect.width - 16;
    if (bottom > window.innerHeight - 16) top = window.innerHeight - rect.height - 16;
    if (left < 8) left = 8;
    if (top < 8) top = 8;
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
  }, [position, users]);

  const toggleUser = (userId: string) => {
    setSelectedUserIds((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId],
    );
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (selectedUserIds.length === 0) return;

    // Build datetimes — handle overnight (end < start → next day)
    let endDate = dateStr;
    if (!shiftType?.is_absence && endTime <= startTime && startTime !== '00:00') {
      endDate = format(addDays(parseISO(dateStr), 1), 'yyyy-MM-dd');
    }
    const startDatetime = `${dateStr}T${startTime}:00`;
    const endDatetime = `${endDate}T${endTime}:00`;

    onConfirm({
      shiftTypeId,
      userIds: selectedUserIds,
      startDatetime,
      endDatetime,
      notes: notes.trim() || undefined,
      location: location.trim() || undefined,
      grat_type: gratType.trim() || undefined,
    });
  };

  const needsTimeInput = !shiftType?.fixed_slots && !shiftType?.is_absence;
  const isAbsence = shiftType?.is_absence ?? false;

  // Filter to militares only (exclude admin/secretaria who don't do shifts)
  const isNormalService = !_NON_SERVICE_CODES.has(shiftType?.code ?? '');

  // Users already assigned to a normal service on this day
  const alreadyAssignedIds = isNormalService
    ? new Set(
        existingShifts
          .filter(
            (s) =>
              s.status !== 'cancelled' &&
              s.shift_type_code &&
              !_NON_SERVICE_CODES.has(s.shift_type_code),
          )
          .map((s) => s.user_id),
      )
    : new Set<string>();

  const assignableUsers = users.filter(
    (u) =>
      (u.role === 'militar' || u.role === 'comandante' || u.role === 'adjunto') &&
      !alreadyAssignedIds.has(u.id),
  );

  return (
    <>
      <div className="apop-overlay" onClick={onClose} />
      <div
        className="apop-container"
        ref={popoverRef}
        style={{ left: position.x, top: position.y }}
      >
        {/* Header */}
        <div className="apop-header" style={{ borderLeftColor: shiftType?.color ?? '#6B7280' }}>
          <div className="apop-header-info">
            <span className="apop-type-code" style={{ color: shiftType?.color }}>
              {shiftType?.code ?? '…'}
            </span>
            <span className="apop-type-name">{shiftType?.name ?? 'A carregar…'}</span>
            <span className="apop-date">{format(date, 'dd/MM/yyyy')}</span>
          </div>
          <button className="btn-icon apop-close" onClick={onClose} disabled={isPending}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="apop-body">
          {/* Time inputs — only for GRAT and similar free-form types */}
          {needsTimeInput && (
            <div className="apop-times">
              <div className="apop-time-field">
                <Clock size={13} />
                <label>Início</label>
                <input
                  type="time"
                  className="input-field apop-time-input"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  required
                />
              </div>
              <span className="apop-time-sep">→</span>
              <div className="apop-time-field">
                <Clock size={13} />
                <label>Fim</label>
                <input
                  type="time"
                  className="input-field apop-time-input"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          {/* Fixed slot times shown read-only */}
          {shiftType?.fixed_slots && (
            <div className="apop-fixed-time">
              <Clock size={13} />
              <span>{startTime} → {endTime}</span>
            </div>
          )}

          {/* All-day badge for absences */}
          {isAbsence && (
            <div className="apop-allday-badge">Dia inteiro</div>
          )}

          {/* GRAT-specific fields: location and gratificado type */}
          {needsTimeInput && (
            <div className="apop-grat-fields">
              <div className="apop-field">
                <MapPin size={13} />
                <label>Localização</label>
                <input
                  type="text"
                  className="input-field"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Ex: Estádio Municipal, Rua X..."
                />
              </div>
              <div className="apop-field">
                <Tag size={13} />
                <label>Tipo de Gratificado</label>
                <input
                  type="text"
                  className="input-field"
                  value={gratType}
                  onChange={(e) => setGratType(e.target.value)}
                  placeholder="Ex: Evento desportivo, Segurança privada..."
                />
              </div>
            </div>
          )}

          {/* Notes — available for all services */}
          <div className="apop-field apop-notes-field">
            <FileText size={13} />
            <label>Notas</label>
            <textarea
              className="input-field"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Indicações, giro, observações..."
              rows={2}
              maxLength={2000}
            />
          </div>

          {/* User selection */}
          <div className="apop-user-section">
            <span className="apop-section-label">
              Selecionar militar{assignableUsers.length !== 1 ? 'es' : ''}
              {shiftType?.min_staff && shiftType.min_staff > 1
                ? ` (mín. ${shiftType.min_staff})`
                : ''}
            </span>
            <div className="apop-user-list">
              {assignableUsers.length === 0 ? (
                <span className="apop-empty">Nenhum militar disponível</span>
              ) : (
                assignableUsers.map((u) => (
                  <label key={u.id} className="apop-user-item">
                    <input
                      type="checkbox"
                      checked={selectedUserIds.includes(u.id)}
                      onChange={() => toggleUser(u.id)}
                      className="apop-checkbox"
                    />
                    <div className="apop-user-info">
                      <span className="apop-user-name">
                        {u.full_name}
                        {u.default_shift_type_id === shiftTypeId && (
                          <span className="apop-fixed-badge" title="Atribuição fixa">fixo</span>
                        )}
                      </span>
                      <span className="apop-user-nip">{u.numero_ordem ?? u.nip}</span>
                    </div>
                  </label>
                ))
              )}
            </div>
          </div>

          <div className="apop-actions">
            {selectedUserIds.length === 0 && (
              <span className="apop-hint">Selecione pelo menos um militar</span>
            )}
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              onClick={onClose}
              disabled={isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn btn-sm btn-primary"
              disabled={isPending || selectedUserIds.length === 0}
            >
              {isPending ? (
                <div className="spinner spinner-sm" />
              ) : (
                <Check size={14} />
              )}
              Atribuir
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
