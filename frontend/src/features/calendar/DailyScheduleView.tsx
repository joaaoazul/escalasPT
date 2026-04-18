/**
 * DailyScheduleView — single-day view showing shifts grouped by time slot.
 * Similar to the daily operational document used in GNR stations.
 */

import { useState, useMemo } from 'react';
import { format, addDays, subDays, isToday, isSameDay } from 'date-fns';
import { pt } from 'date-fns/locale';
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Calendar, MapPin } from 'lucide-react';
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
  isAbsence: boolean;
  /** Extra metadata for GRAT/INST sub-groups */
  gratType?: string;
  location?: string;
  color?: string;
}

export function DailyScheduleView({
  shifts,
  selectedDate,
  onDateChange,
  onShiftClick,
  isLoading,
}: DailyScheduleViewProps) {
  const dateStr = format(selectedDate, 'yyyy-MM-dd');
  const [collapsedSlots, setCollapsedSlots] = useState<Set<string>>(new Set());

  const toggleSlot = (key: string) => {
    setCollapsedSlots((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const dayShifts = useMemo(() => {
    return shifts
      .filter((s) => s.date === dateStr && s.status !== 'cancelled')
      .sort((a, b) => a.start_datetime.localeCompare(b.start_datetime));
  }, [shifts, dateStr]);

  // Codes that appear as inline chips (absences and simple full-day types)
  const inlineCodes = ['CONV', 'DIL', 'F', 'FER', 'LIC', 'MF', 'T'];

  // Codes that need sub-grouping by grat_type + location + time
  const detailCodes = ['GRAT', 'INST'];

  // Group shifts into service slots, inline absences
  const { serviceSlots, inlineSlots } = useMemo(() => {
    const slotMap = new Map<string, TimeSlotGroup>();
    const detailShifts: Shift[] = [];

    dayShifts.forEach((s) => {
      const code = (s.shift_type_code ?? '').toUpperCase();
      if (inlineCodes.includes(code)) {
        const key = s.shift_type_id ?? 'other';
        if (!slotMap.has(key)) {
          slotMap.set(key, {
            label: s.shift_type_code ?? s.shift_type_name ?? 'Turno',
            range: '',
            shifts: [],
            isAbsence: true,
          });
        }
        slotMap.get(key)!.shifts.push(s);
      } else if (detailCodes.includes(code)) {
        detailShifts.push(s);
      } else {
        const key = s.shift_type_id ?? 'other';
        if (!slotMap.has(key)) {
          slotMap.set(key, {
            label: s.shift_type_code ?? s.shift_type_name ?? 'Turno',
            range: `${formatTime(s.start_datetime)} — ${formatTime(s.end_datetime)}`,
            shifts: [],
            isAbsence: false,
          });
        }
        slotMap.get(key)!.shifts.push(s);
      }
    });

    // Sub-group GRAT/INST by grat_type + location + time
    const detailGroups = new Map<string, TimeSlotGroup>();
    for (const s of detailShifts) {
      const code = (s.shift_type_code ?? '').toUpperCase();
      const subKey = `${code}|${s.grat_type ?? ''}|${s.location ?? ''}|${formatTime(s.start_datetime)}-${formatTime(s.end_datetime)}`;
      if (!detailGroups.has(subKey)) {
        detailGroups.set(subKey, {
          label: code,
          range: `${formatTime(s.start_datetime)} — ${formatTime(s.end_datetime)}`,
          shifts: [],
          isAbsence: false,
          gratType: s.grat_type ?? '',
          location: s.location ?? '',
          color: s.shift_type_color ?? undefined,
        });
      }
      detailGroups.get(subKey)!.shifts.push(s);
    }

    const all = Array.from(slotMap.entries());

    // Service slots: regular + detail sub-groups
    const regular = all
      .filter(([, g]) => !g.isAbsence)
      .sort(([, a], [, b]) => {
        const aTime = a.shifts[0]?.start_datetime ?? '';
        const bTime = b.shifts[0]?.start_datetime ?? '';
        return aTime.localeCompare(bTime);
      });

    const detail: [string, TimeSlotGroup][] = Array.from(detailGroups.entries())
      .sort(([, a], [, b]) => {
        const aTime = a.shifts[0]?.start_datetime ?? '';
        const bTime = b.shifts[0]?.start_datetime ?? '';
        return aTime.localeCompare(bTime);
      });

    const inline = all
      .filter(([, g]) => g.isAbsence)
      .sort(([, a], [, b]) => a.label.localeCompare(b.label));

    return { regularSlots: regular, detailSlots: detail, inlineSlots: inline };
  }, [dayShifts]);

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
          {/* Regular service shifts (AT, OC, SEC, INQ, etc.) */}
          {regularSlots.length > 0 && (
            <div className="daily-view-section">
              <div className="daily-view-section-title">Turnos</div>
              <div className="daily-view-table">
                <div className="daily-view-table-header">
                  <span className="daily-view-th-type">Tipo</span>
                  <span className="daily-view-th-time">Horário</span>
                  <span className="daily-view-th-staff">Efetivo</span>
                </div>
                {regularSlots.map(([key, slot]) => {
                  const isCollapsed = collapsedSlots.has(key);
                  const slotColor = slot.shifts[0]?.shift_type_color ?? 'var(--color-primary-400)';
                  return (
                    <div key={key} className="daily-view-slot">
                      <button
                        className="daily-view-slot-header daily-view-slot-toggle"
                        onClick={() => toggleSlot(key)}
                        type="button"
                      >
                        <span className="daily-view-slot-header-left">
                          <span
                            className="daily-view-slot-code"
                            style={{ color: slotColor }}
                          >
                            {slot.label}
                          </span>
                        </span>
                        <span className="daily-view-slot-range">{slot.range}</span>
                        <span className="daily-view-slot-header-right">
                          <span className="daily-view-slot-count">{slot.shifts.length}</span>
                          {isCollapsed ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
                        </span>
                      </button>
                      {!isCollapsed && (
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
                                style={{ backgroundColor: slotColor }}
                              />
                              <span className="daily-view-member-num">
                                {s.user_numero_ordem ?? '—'}
                              </span>
                              <span className="daily-view-member-name">{s.user_name ?? '?'}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* GRAT / INST — detail services */}
          {detailSlots.length > 0 && (
            <div className="daily-view-section">
              <div className="daily-view-section-title">Gratificados &amp; Instrução</div>
              <div className="daily-view-table">
                <div className="daily-view-table-header">
                  <span className="daily-view-th-type">Tipo</span>
                  <span className="daily-view-th-time">Horário</span>
                  <span className="daily-view-th-staff">Efetivo</span>
                </div>
                {detailSlots.map(([key, slot]) => {
                  const isCollapsed = collapsedSlots.has(key);
                  const slotColor = slot.color ?? slot.shifts[0]?.shift_type_color ?? 'var(--color-primary-400)';
                  return (
                    <div key={key} className="daily-view-slot">
                      <button
                        className="daily-view-slot-header daily-view-slot-toggle"
                        onClick={() => toggleSlot(key)}
                        type="button"
                      >
                        <span className="daily-view-slot-header-left">
                          <span
                            className="daily-view-slot-code"
                            style={{ color: slotColor }}
                          >
                            {slot.label}
                          </span>
                          {slot.gratType && (
                            <span className="daily-view-slot-detail-tag">{slot.gratType}</span>
                          )}
                        </span>
                        <span className="daily-view-slot-range">{slot.range}</span>
                        <span className="daily-view-slot-header-right">
                          <span className="daily-view-slot-count">{slot.shifts.length}</span>
                          {isCollapsed ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
                        </span>
                      </button>
                      {!isCollapsed && (
                        <>
                          {slot.location && (
                            <div className="daily-view-slot-location">
                              <MapPin size={12} /> {slot.location}
                            </div>
                          )}
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
                                  style={{ backgroundColor: slotColor }}
                                />
                                <span className="daily-view-member-num">
                                  {s.user_numero_ordem ?? '—'}
                                </span>
                                <span className="daily-view-member-name">{s.user_name ?? '?'}</span>
                              </button>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Ausências & Outros — inline chips */}
          {inlineSlots.length > 0 && (
            <div className="daily-view-section">
              <div className="daily-view-section-title">Ausências &amp; Outros</div>
              <div className="daily-view-absence-inline">
                {inlineSlots.map(([key, group]) => (
                  <div key={key} className="daily-view-absence-row">
                    <span
                      className="daily-view-absence-code-inline"
                      style={{ color: group.shifts[0]?.shift_type_color ?? 'var(--text-muted)' }}
                    >
                      {group.label}
                    </span>
                    <div className="daily-view-absence-chips">
                      {group.shifts.map((s) => (
                        <button
                          key={s.id}
                          className="daily-view-absence-chip"
                          onClick={() => onShiftClick(s)}
                          type="button"
                        >
                          <span className="daily-view-chip-num">{s.user_numero_ordem ?? '—'}</span>
                          <span className="daily-view-chip-name">{s.user_name ?? '?'}</span>
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
                {regularSlots.reduce((n, [, g]) => n + g.shifts.length, 0) +
                  detailSlots.reduce((n, [, g]) => n + g.shifts.length, 0)}
              </span>
            </div>
            <div className="daily-view-summary-item">
              <span>Ausências</span>
              <span className="daily-view-summary-val">
                {inlineSlots.reduce((n, [, g]) => n + g.shifts.length, 0)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
