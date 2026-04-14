/**
 * SwapRequestModal — bidirectional swap proposal modal.
 *
 * Mode A (myShift preset): A's own shift is fixed; user picks a target shift from the station.
 * Mode B (targetShift preset): The target shift is fixed (clicked from patrol panel);
 *                               user picks which of THEIR OWN shifts to offer.
 *
 * Call with exactly one of the two preset props.
 */

import { useState, type FormEvent } from 'react';
import { X, ArrowLeftRight, Calendar, Clock, AlertCircle } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { pt } from 'date-fns/locale';
import { useQuery } from '@tanstack/react-query';
import { fetchShifts } from '../../api/shifts';
import { useCreateSwap } from '../../hooks/useSwaps';
import { useAuth } from '../../hooks/useAuth';
import type { Shift } from '../../types';
import './SwapRequestModal.css';

/** Absence codes that CANNOT be swapped (backend also enforces this). */
const NON_SWAPPABLE_CODES = new Set(['FER', 'CONV', 'MF', 'DIL', 'LIC']);

function isSwappable(s: Shift): boolean {
  return !s.shift_type_code || !NON_SWAPPABLE_CODES.has(s.shift_type_code);
}

interface SwapRequestModalProps {
  /** Mode A: the requesting military's own shift is pre-selected; user picks target. */
  myShift?: Shift;
  /** Mode B: the target shift is pre-selected (from patrol panel); user picks their own shift. */
  targetShift?: Shift;
  onClose: () => void;
}

function fmtTime(dt: string | null) {
  if (!dt) return '—';
  const clean = dt.replace(/([+-]\d{2}:\d{2}|Z)$/, '');
  try {
    const d = parseISO(clean);
    return isValid(d) ? format(d, 'HH:mm') : '—';
  } catch { return '—'; }
}

function ShiftChip({ shift, label }: { shift: Shift; label: string }) {
  return (
    <div className="swap-shift-preview">
      <span className="swap-preview-label">{label}</span>
      <div className="swap-shift-card">
        <span
          className="swap-shift-dot"
          style={{ background: shift.shift_type_color ?? 'var(--color-primary-500)' }}
        />
        <span className="swap-shift-code">{shift.shift_type_code ?? '—'}</span>
        <span className="swap-shift-date">
          {format(parseISO(shift.date), 'EEE d MMM', { locale: pt })}
        </span>
        <span className="swap-shift-time">
          {fmtTime(shift.start_datetime)} – {fmtTime(shift.end_datetime)}
        </span>
        {shift.user_name && (
          <span className="swap-shift-user">{shift.user_name}</span>
        )}
      </div>
    </div>
  );
}

// ── Mode A: my shift is fixed, pick a target ──────────────

function PickTargetContent({
  myShift,
  onSelected,
}: {
  myShift: Shift;
  onSelected: (s: Shift | null) => void;
}) {
  const [targetDate, setTargetDate] = useState(myShift.date);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['station-shifts-for-swap', myShift.station_id, targetDate],
    queryFn: () =>
      fetchShifts({
        station_id: myShift.station_id,
        date_from: targetDate,
        date_to: targetDate,
        status: 'published',
        limit: 50,
      }),
    enabled: Boolean(myShift.station_id && targetDate),
  });

  const available = (data?.shifts ?? []).filter(
    (s) => s.user_id !== myShift.user_id && s.id !== myShift.id && isSwappable(s),
  );

  const select = (id: string) => {
    const next = id === selectedId ? null : id;
    setSelectedId(next);
    onSelected(next ? available.find((s) => s.id === next) ?? null : null);
  };

  return (
    <>
      <div className="swap-field">
        <label className="swap-field-label">
          <Calendar size={14} /> Data do turno a receber
        </label>
        <input
          type="date"
          className="input"
          value={targetDate}
          onChange={(e) => {
            setTargetDate(e.target.value);
            setSelectedId(null);
            onSelected(null);
          }}
        />
      </div>
      <div className="swap-field">
        <label className="swap-field-label">
          <Clock size={14} /> Turno a receber
        </label>
        {isLoading ? (
          <div className="swap-shift-list-empty"><div className="spinner spinner-sm" /></div>
        ) : available.length === 0 ? (
          <div className="swap-shift-list-empty">
            <AlertCircle size={16} /><span>Sem turnos publicados nesta data</span>
          </div>
        ) : (
          <div className="swap-shift-list">
            {available.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`swap-shift-option ${selectedId === s.id ? 'selected' : ''}`}
                onClick={() => select(s.id)}
              >
                <span className="swap-shift-dot" style={{ background: s.shift_type_color ?? 'var(--color-primary-500)' }} />
                <span className="swap-option-code">{s.shift_type_code ?? '—'}</span>
                <span className="swap-option-user">{s.user_name ?? '—'}</span>
                <span className="swap-option-time">{fmtTime(s.start_datetime)} – {fmtTime(s.end_datetime)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

// ── Mode B: target is fixed, pick one of my own shifts ────

function PickMyShiftContent({
  targetShift,
  onSelected,
}: {
  targetShift: Shift;
  onSelected: (s: Shift | null) => void;
}) {
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['my-published-shifts', user?.id, targetShift.station_id],
    queryFn: () =>
      fetchShifts({
        user_id: user!.id,
        station_id: targetShift.station_id,
        status: 'published',
        limit: 100,
      }),
    enabled: Boolean(user?.id),
  });

  const available = (data?.shifts ?? []).filter(
    (s) => s.id !== targetShift.id && isSwappable(s),
  );

  const select = (id: string) => {
    const next = id === selectedId ? null : id;
    setSelectedId(next);
    onSelected(next ? available.find((s) => s.id === next) ?? null : null);
  };

  return (
    <div className="swap-field">
      <label className="swap-field-label">
        <Clock size={14} /> Qual dos seus turnos quer oferecer?
      </label>
      {isLoading ? (
        <div className="swap-shift-list-empty"><div className="spinner spinner-sm" /></div>
      ) : available.length === 0 ? (
        <div className="swap-shift-list-empty">
          <AlertCircle size={16} /><span>Não tem turnos publicados disponíveis</span>
        </div>
      ) : (
        <div className="swap-shift-list">
          {available.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`swap-shift-option ${selectedId === s.id ? 'selected' : ''}`}
              onClick={() => select(s.id)}
            >
              <span className="swap-shift-dot" style={{ background: s.shift_type_color ?? 'var(--color-primary-500)' }} />
              <span className="swap-option-code">{s.shift_type_code ?? '—'}</span>
              <span className="swap-option-time">
                {format(parseISO(s.date), 'EEE d MMM', { locale: pt })}
                {' · '}
                {fmtTime(s.start_datetime)}–{fmtTime(s.end_datetime)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main modal ────────────────────────────────────────────

export function SwapRequestModal({ myShift, targetShift, onClose }: SwapRequestModalProps) {
  const [pickedShift, setPickedShift] = useState<Shift | null>(null);
  const [reason, setReason] = useState('');
  const { mutate: createSwap, isPending } = useCreateSwap();

  const isModeA = Boolean(myShift && !targetShift);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!pickedShift) return;

    let requesterShiftId: string;
    let targetShiftId: string;
    let targetId: string;

    if (isModeA && myShift) {
      // A's own shift → offering to swap with the picked target
      requesterShiftId = myShift.id;
      targetShiftId = pickedShift.id;
      targetId = pickedShift.user_id;
    } else if (targetShift) {
      // Target is preset → picked shift is A's offering
      requesterShiftId = pickedShift.id;
      targetShiftId = targetShift.id;
      targetId = targetShift.user_id;
    } else {
      return;
    }

    createSwap(
      {
        requester_shift_id: requesterShiftId,
        target_shift_id: targetShiftId,
        target_id: targetId,
        reason: reason.trim() || undefined,
      },
      { onSuccess: onClose },
    );
  };

  return (
    <>
      <div className="modal-overlay" onClick={onClose} />
      <div className="swap-modal animate-slide-in">
        {/* Header */}
        <div className="swap-modal-header">
          <div className="swap-modal-title-row">
            <ArrowLeftRight size={18} />
            <h2 className="swap-modal-title">Propor Troca de Turno</h2>
          </div>
          <button className="btn-icon" onClick={onClose} title="Fechar">
            <X size={18} />
          </button>
        </div>

        <div className="swap-modal-body">
          {isModeA && myShift ? (
            <>
              <ShiftChip shift={myShift} label="O meu turno" />
              <div className="swap-arrow-divider"><ArrowLeftRight size={16} /></div>
              <PickTargetContent myShift={myShift} onSelected={setPickedShift} />
            </>
          ) : targetShift ? (
            <>
              <ShiftChip shift={targetShift} label="Turno a receber" />
              <div className="swap-arrow-divider"><ArrowLeftRight size={16} /></div>
              <PickMyShiftContent targetShift={targetShift} onSelected={setPickedShift} />
            </>
          ) : null}

          {/* Reason */}
          <div className="swap-field">
            <label className="swap-field-label">Motivo (opcional)</label>
            <textarea
              className="input swap-reason"
              placeholder="Indica o motivo do pedido…"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={500}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="swap-modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isPending}>
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            disabled={!pickedShift || isPending}
            onClick={handleSubmit}
          >
            {isPending ? <span className="spinner spinner-sm" /> : null}
            Enviar Pedido
          </button>
        </div>
      </div>
    </>
  );
}

