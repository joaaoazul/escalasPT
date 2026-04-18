/**
 * DailyScheduleView — single-day view showing shifts grouped by time slot.
 * Similar to the daily operational document used in GNR stations.
 */

import { useMemo } from 'react';
import { format, addDays, subDays, isToday, isSameDay } from 'date-fns';
import { pt } from 'date-fns/locale';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import type { Shift } from '../../types';
import { formatTime } from '../../utils/helpers';
import './DailyScheduleView.css';

interface DailyScheduleViewProps {
  shifts: Shift[];
  selectedDate: Date;
  onDateChange: (date: Date) => void;
  onShiftClick: (shift: Shift) => void;
  isLoading: boolean;
}

interface TimeSlotGroup {
  label: string;
  range: string;
  shifts: Shift[];
}

export function DailyScheduleView({
  shifts,
  selectedDate,
  onDateChange,
  onShiftClick,
  isLoading,
}: DailyScheduleViewProps) {
  const dateStr = format(selectedDate, 'yyyy-MM-dd');

  const dayShifts = useMemo(() => {
    return shifts
      .filter((s) => s.date === dateStr && s.status !== 'cancelled')
      .sort((a, b) => a.start_datetime.localeCompare(b.start_datetime));
  }, [shifts, dateStr]);

  // Group shifts into time slots and absences
  const { regularSlots, absences } = useMemo(() => {
    const regular: Shift[] = [];
    const abs: Shift[] = [];

    dayShifts.forEach((s) => {
      // Check if it's an absence type by checking is_absence-related codes
      const code = (s.shift_type_code ?? '').toUpperCase();
      const absenceCodes = ['CONV', 'DIL', 'F', 'FER', 'LIC', 'MF', 'GRAT', 'INST', 'T'];
      if (absenceCodes.includes(code)) {
        abs.push(s);
      } else {
        regular.push(s);
      }
    });

    // Group regular shifts by shift type
    const slotMap = new Map<string, TimeSlotGroup>();
    regular.forEach((s) => {
      const key = s.shift_type_id ?? 'other';
      if (!slotMap.has(key)) {
        slotMap.set(key, {
          label: s.shift_type_code ?? s.shift_type_name ?? 'Turno',
          range: `${formatTime(s.start_datetime)} — ${formatTime(s.end_datetime)}`,
          shifts: [],
        });
      }
      slotMap.get(key)!.shifts.push(s);
    });

    // Sort by start time
    const slots = Array.from(slotMap.values()).sort((a, b) => {
      const aTime = a.shifts[0]?.start_datetime ?? '';
      const bTime = b.shifts[0]?.start_datetime ?? '';
      return aTime.localeCompare(bTime);
    });

    return { regularSlots: slots, absences: abs };
  }, [dayShifts]);

  // Group absences by type
  const absenceGroups = useMemo(() => {
    const map = new Map<string, Shift[]>();
    absences.forEach((s) => {
      const code = s.shift_type_code ?? 'Outro';
      if (!map.has(code)) map.set(code, []);
      map.get(code)!.push(s);
    });
    return Array.from(map.entries());
  }, [absences]);

  if (isLoading) {
    return (
      <div className="station-loading">
        <div className="spinner spinner-lg" />
        <span>A carregar escala do dia...</span>
      </div>
    );
  }

  return (
    <div className="daily-view">
      {/* Day navigation */}
      <div className="daily-view-nav">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onDateChange(subDays(selectedDate, 1))}
        >
          <ChevronLeft size={16} />
        </button>
        <div className="daily-view-date">
          <Calendar size={15} />
          <span className="daily-view-date-text">
            {format(selectedDate, "EEEE, d 'de' MMMM 'de' yyyy", { locale: pt })}
          </span>
          {isToday(selectedDate) && <span className="daily-view-today-badge">Hoje</span>}
        </div>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onDateChange(addDays(selectedDate, 1))}
        >
          <ChevronRight size={16} />
        </button>
        {!isSameDay(selectedDate, new Date()) && (
          <button
            className="btn btn-ghost btn-sm daily-view-goto-today"
            onClick={() => onDateChange(new Date())}
          >
            Hoje
          </button>
        )}
      </div>

      {dayShifts.length === 0 ? (
        <div className="daily-view-empty">
          <span>Sem turnos para este dia</span>
        </div>
      ) : (
        <div className="daily-view-content">
          {/* Regular shifts by type */}
          {regularSlots.length > 0 && (
            <div className="daily-view-section">
              <div className="daily-view-section-title">Turnos</div>
              <div className="daily-view-table">
                <div className="daily-view-table-header">
                  <span className="daily-view-th-type">Tipo</span>
                  <span className="daily-view-th-time">Horário</span>
                  <span className="daily-view-th-staff">Efetivo</span>
                </div>
                {regularSlots.map((slot) => (
                  <div key={slot.label} className="daily-view-slot">
                    <div className="daily-view-slot-header">
                      <span
                        className="daily-view-slot-code"
                        style={{
                          color: slot.shifts[0]?.shift_type_color ?? 'var(--color-primary-400)',
                        }}
                      >
                        {slot.label}
                      </span>
                      <span className="daily-view-slot-range">{slot.range}</span>
                      <span className="daily-view-slot-count">{slot.shifts.length}</span>
                    </div>
                    <div className="daily-view-slot-members">
                      {slot.shifts.map((s) => (
                        <button
                          key={s.id}
                          className="daily-view-member"
                          onClick={() => onShiftClick(s)}
                          type="button"
                        >
                          <span
                            className="daily-view-member-dot"
                            style={{
                              backgroundColor: s.shift_type_color ?? 'var(--color-primary-500)',
                            }}
                          />
                          <span className="daily-view-member-num">
                            {s.user_numero_ordem ?? '—'}
                          </span>
                          <span className="daily-view-member-name">{s.user_name ?? '?'}</span>
                          {s.location && (
                            <span className="daily-view-member-loc">{s.location}</span>
                          )}
                          {s.grat_type && (
                            <span className="daily-view-member-grat">{s.grat_type}</span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Absences / Other */}
          {absenceGroups.length > 0 && (
            <div className="daily-view-section">
              <div className="daily-view-section-title">Ausências &amp; Outros</div>
              <div className="daily-view-absence-grid">
                {absenceGroups.map(([code, groupShifts]) => (
                  <div key={code} className="daily-view-absence-group">
                    <div
                      className="daily-view-absence-code"
                      style={{
                        color: groupShifts[0]?.shift_type_color ?? 'var(--text-muted)',
                      }}
                    >
                      {code}
                    </div>
                    <div className="daily-view-absence-members">
                      {groupShifts.map((s) => (
                        <button
                          key={s.id}
                          className="daily-view-absence-member"
                          onClick={() => onShiftClick(s)}
                          type="button"
                        >
                          <span className="daily-view-member-num">
                            {s.user_numero_ordem ?? '—'}
                          </span>
                          <span className="daily-view-member-name">{s.user_name ?? '?'}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="daily-view-summary">
            <div className="daily-view-summary-item">
              <span>Total de turnos</span>
              <span className="daily-view-summary-val">{dayShifts.length}</span>
            </div>
            <div className="daily-view-summary-item">
              <span>Em serviço</span>
              <span className="daily-view-summary-val">
                {dayShifts.length - absences.length}
              </span>
            </div>
            <div className="daily-view-summary-item">
              <span>Ausências</span>
              <span className="daily-view-summary-val">{absences.length}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
