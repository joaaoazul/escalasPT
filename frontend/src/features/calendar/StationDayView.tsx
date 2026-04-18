/**
 * StationDayView — station-wide schedule grouped by day, then by shift type.
 * Each day is collapsible. Within a day, shifts are grouped by type showing
 * assigned personnel underneath — much cleaner on mobile.
 */

import { useMemo, useState } from 'react';
import { format, eachDayOfInterval, startOfMonth, endOfMonth, isToday } from 'date-fns';
import { pt } from 'date-fns/locale';
import { ChevronDown, ChevronRight, Users } from 'lucide-react';
import type { Shift } from '../../types';
import { formatTime, getInitials } from '../../utils/helpers';
import './StationDayView.css';

interface StationDayViewProps {
  shifts: Shift[];
  currentMonth: Date;
  onShiftClick: (shift: Shift) => void;
  isLoading: boolean;
}

interface ShiftTypeGroup {
  code: string;
  name: string;
  color: string;
  range: string;
  shifts: Shift[];
}

interface DayGroup {
  date: Date;
  dateStr: string;
  shiftGroups: ShiftTypeGroup[];
  totalShifts: number;
}

export function StationDayView({
  shifts,
  currentMonth,
  onShiftClick,
  isLoading,
}: StationDayViewProps) {
  const todayStr = format(new Date(), 'yyyy-MM-dd');
  const [expandedDays, setExpandedDays] = useState<Set<string>>(() => new Set([todayStr]));

  const toggleDay = (dateStr: string) => {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(dateStr)) next.delete(dateStr);
      else next.add(dateStr);
      return next;
    });
  };

  const dayGroups: DayGroup[] = useMemo(() => {
    const start = startOfMonth(currentMonth);
    const end = endOfMonth(currentMonth);
    const days = eachDayOfInterval({ start, end });

    return days.map((day) => {
      const dayStr = format(day, 'yyyy-MM-dd');
      const dayShifts = shifts
        .filter((s) => s.date === dayStr && s.status !== 'cancelled')
        .sort((a, b) => a.start_datetime.localeCompare(b.start_datetime));

      // Group by shift_type_id
      const typeMap = new Map<string, ShiftTypeGroup>();
      for (const s of dayShifts) {
        const key = s.shift_type_id ?? 'other';
        if (!typeMap.has(key)) {
          typeMap.set(key, {
            code: s.shift_type_code ?? s.shift_type_name ?? 'Turno',
            name: s.shift_type_name ?? '',
            color: s.shift_type_color ?? '#3B82F6',
            range: `${formatTime(s.start_datetime)} — ${formatTime(s.end_datetime)}`,
            shifts: [],
          });
        }
        typeMap.get(key)!.shifts.push(s);
      }

      return {
        date: day,
        dateStr: dayStr,
        shiftGroups: Array.from(typeMap.values()),
        totalShifts: dayShifts.length,
      };
    });
  }, [shifts, currentMonth]);

  if (isLoading) {
    return (
      <div className="station-loading">
        <div className="spinner spinner-lg" />
        <span>A carregar escala do posto...</span>
      </div>
    );
  }

  return (
    <div className="sdv">
      {dayGroups.map((group) => {
        const isExpanded = expandedDays.has(group.dateStr);
        const today = isToday(group.date);
        const empty = group.totalShifts === 0;

        return (
          <div
            key={group.dateStr}
            className={`sdv-day${today ? ' sdv-today' : ''}${empty ? ' sdv-empty' : ''}`}
          >
            <button
              className="sdv-day-header"
              onClick={() => toggleDay(group.dateStr)}
              type="button"
            >
              <div className="sdv-day-left">
                <span className="sdv-day-num">{format(group.date, 'dd')}</span>
                <span className="sdv-day-name">
                  {format(group.date, 'EEEE', { locale: pt })}
                </span>
                {today && <span className="sdv-badge-today">Hoje</span>}
              </div>
              <div className="sdv-day-right">
                {group.totalShifts > 0 && (
                  <span className="sdv-day-count">{group.totalShifts}</span>
                )}
                {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </div>
            </button>

            {isExpanded && group.totalShifts > 0 && (
              <div className="sdv-groups">
                {group.shiftGroups.map((sg, i) => (
                  <div key={i} className="sdv-type-group">
                    <div className="sdv-type-header">
                      <span
                        className="sdv-type-bar"
                        style={{ backgroundColor: sg.color }}
                      />
                      <span className="sdv-type-code" style={{ color: sg.color }}>
                        {sg.code}
                      </span>
                      <span className="sdv-type-time">{sg.range}</span>
                      <span className="sdv-type-count">
                        <Users size={11} />
                        {sg.shifts.length}
                      </span>
                    </div>
                    <div className="sdv-members">
                      {sg.shifts.map((s) => (
                        <button
                          key={s.id}
                          className="sdv-member"
                          onClick={() => onShiftClick(s)}
                          type="button"
                        >
                          <div
                            className="sdv-member-avatar"
                            style={{ backgroundColor: sg.color }}
                          >
                            {getInitials(s.user_name ?? '?')}
                          </div>
                          <span className="sdv-member-name">{s.user_name ?? '?'}</span>
                          {s.user_numero_ordem && (
                            <span className="sdv-member-num">#{s.user_numero_ordem}</span>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {isExpanded && group.totalShifts === 0 && (
              <div className="sdv-no-shifts">Sem turnos</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
