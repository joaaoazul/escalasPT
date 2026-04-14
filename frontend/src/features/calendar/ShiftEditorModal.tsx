/**
 * ShiftEditorModal — modal for creating and editing shifts.
 */

import { useState, useEffect, type FormEvent } from 'react';
import { X, Calendar, User, FileText, Tag } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { useStationUsers } from '../../hooks/useStationUsers';
import { useShiftTypes } from '../../hooks/useShiftTypes';
import { useShiftMutations } from '../../hooks/useShiftMutations';
import type { Shift } from '../../types';
import './ShiftEditorModal.css';

interface ShiftEditorModalProps {
  shift?: Shift | null; // If passed, it's edit mode
  initialDate?: Date;   // If passed without shift, it's create mode
  onClose: () => void;
}

export function ShiftEditorModal({
  shift,
  initialDate,
  onClose,
}: ShiftEditorModalProps) {
  const { data: users = [], isLoading: isLoadingUsers } = useStationUsers();
  const { data: shiftTypes = [], isLoading: isLoadingTypes } = useShiftTypes();
  const { createShift, updateShift } = useShiftMutations();

  // Form state
  const [userId, setUserId] = useState('');
  const [shiftTypeId, setShiftTypeId] = useState('');
  const [date, setDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [notes, setNotes] = useState('');

  const isEdit = !!shift;

  // Initialize form
  useEffect(() => {
    if (shift) {
      setUserId(shift.user_id);
      setShiftTypeId(shift.shift_type_id ?? '');
      setDate(shift.date);
      setStartTime(shift.start_datetime.substring(11, 16)); // "HH:mm" from "YYYY-MM-DDTHH:mm:ss"
      setEndTime(shift.end_datetime.substring(11, 16));
      setNotes(shift.notes ?? '');
    } else if (initialDate) {
      setDate(format(initialDate, 'yyyy-MM-dd'));
      setStartTime('08:00');
      setEndTime('16:00');
    }
  }, [shift, initialDate]);

  // Pre-fill times based on selected shift type
  const handleShiftTypeChange = (value: string) => {
    setShiftTypeId(value);
    const selected = shiftTypes.find((t) => t.id === value);
    if (!selected) return;
    if (selected.is_absence) {
      setStartTime('00:00');
      setEndTime('00:00');
    } else if (selected.start_time && selected.end_time) {
      setStartTime(selected.start_time.substring(0, 5));
      setEndTime(selected.end_time.substring(0, 5));
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    const start_datetime = `${date}T${startTime}:00`;
    // If end time is before start time, it assumes it crosses midnight (next day)
    // The backend handles the exact logic, we just send valid datetimes.
    // However, basic ISO requires full datetimes.
    // If end_time < start_time, add 1 day to end_date.
    let endDate = date;
    if (endTime < startTime) {
      const nextDay = new Date(parseISO(date));
      nextDay.setDate(nextDay.getDate() + 1);
      endDate = format(nextDay, 'yyyy-MM-dd');
    }
    const end_datetime = `${endDate}T${endTime}:00`;

    if (isEdit && shift) {
      updateShift.mutate(
        {
          id: shift.id,
          data: {
            shift_type_id: shiftTypeId || undefined,
            date,
            start_datetime,
            end_datetime,
            notes: notes || undefined,
          },
        },
        { onSuccess: onClose }
      );
    } else {
      createShift.mutate(
        {
          user_id: userId,
          shift_type_id: shiftTypeId || undefined,
          date,
          start_datetime,
          end_datetime,
          notes: notes || undefined,
        },
        { onSuccess: onClose }
      );
    }
  };

  const selectedShiftType = shiftTypes.find((t) => t.id === shiftTypeId);
  const isAbsenceType = selectedShiftType?.is_absence ?? false;
  const isPending = createShift.isPending || updateShift.isPending;

  return (
    <>
      <div className="modal-overlay" onClick={isPending ? undefined : onClose} />
      <div className="modal-container animate-scale-in">
        <div className="modal-header">
          <h2 className="modal-title">
            {isEdit ? 'Editar Turno' : 'Novo Turno'}
          </h2>
          <button
            className="btn-icon"
            onClick={onClose}
            disabled={isPending}
            title="Fechar"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <div className="input-group">
            <label className="input-label" htmlFor="sem-user">
              Militar
            </label>
            <div className="input-icon-group">
              <select
                id="sem-user"
                className="input-field input-with-icon"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                required
                disabled={isEdit || isPending || isLoadingUsers}
              >
                <option value="" disabled>Selecionar militar...</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                     {u.full_name}
                  </option>
                ))}
              </select>
              <span className="input-icon">
                <User size={18} />
              </span>
            </div>
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="sem-type">
              Tipo de Turno
            </label>
            <div className="input-icon-group">
              <select
                id="sem-type"
                className="input-field input-with-icon"
                value={shiftTypeId}
                onChange={(e) => handleShiftTypeChange(e.target.value)}
                disabled={isPending || isLoadingTypes}
                required
              >
                <option value="" disabled>Selecionar tipo...</option>
                {shiftTypes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.code})
                  </option>
                ))}
              </select>
              <span className="input-icon">
                <Tag size={18} />
              </span>
            </div>
          </div>

          <div className="sem-row">
            <div className="input-group" style={{ flex: 1 }}>
              <label className="input-label" htmlFor="sem-date">
                Data
              </label>
              <div className="input-icon-group">
                <input
                  id="sem-date"
                  type="date"
                  className="input-field input-with-icon"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  required
                  disabled={isPending}
                />
                <span className="input-icon">
                  <Calendar size={18} />
                </span>
              </div>
            </div>

            {isAbsenceType ? (
              <div className="sem-allday-badge">Dia inteiro</div>
            ) : (
              <div className="sem-time-group">
                <div className="input-group">
                  <label className="input-label" htmlFor="sem-start">
                    Início
                  </label>
                  <input
                    id="sem-start"
                    type="time"
                    className="input-field"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    required
                    disabled={isPending}
                  />
                </div>
                <div className="input-group">
                  <label className="input-label" htmlFor="sem-end">
                    Fim
                  </label>
                  <input
                    id="sem-end"
                    type="time"
                    className="input-field"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    required
                    disabled={isPending}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="sem-notes">
              Notas ou Indicações (Opcional)
            </label>
            <div className="input-icon-group" style={{ alignItems: 'flex-start' }}>
              <textarea
                id="sem-notes"
                className="input-field input-with-icon"
                style={{ minHeight: '80px', paddingTop: 'var(--space-3)' }}
                placeholder="Exemplo: Fazer giro na EN10..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={isPending}
              />
              <span className="input-icon" style={{ top: 'var(--space-4)', transform: 'none' }}>
                <FileText size={18} />
              </span>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={isPending}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isPending || !userId || !date || !startTime || !endTime}
            >
              {isPending ? (
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
              ) : isEdit ? (
                'Gravar Alterações'
              ) : (
                'Criar Turno'
              )}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
