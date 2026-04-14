/**
 * StationDayView — station-wide schedule grouped by day.
 * Shows all military members' shifts for each day in a list view.
 */

import { useMemo } from 'react';
import { format, eachDayOfInterval, startOfMonth, endOfMonth, isToday } from 'date-fns';
import { pt } from 'date-fns/locale';
import { Clock, FileText } from 'lucide-react';
import type { Shift } from '../../types';
import { formatTime, getInitials } from '../../utils/helpers';
import './StationDayView.css';

interface StationDayViewProps {
  shifts: Shift[];
  currentMonth: Date;
  onShiftClick: (shift: Shift) => void;
  isLoading: boolean;
}

interface DayGroup {
  date: Date;
  dateStr: string;
  shifts: Shift[];
}

export function StationDayView({
  shifts,
  currentMonth,
  onShiftClick,
  isLoading,
}: StationDayViewProps) {
  const dayGroups: DayGroup[] = useMemo(() => {
    const start = startOfMonth(currentMonth);
    const end = endOfMonth(currentMonth);
    const days = eachDayOfInterval({ start, end });

    return days.map((day) => {
      const dayStr = format(day, 'yyyy-MM-dd');
      const dayShifts = shifts
        .filter((s) => s.date === dayStr)
        .sort((a, b) => a.start_datetime.localeCompare(b.start_datetime));

      return {
        date: day,
        dateStr: dayStr,
        shifts: dayShifts,
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
    <div className="station-day-view">
      {dayGroups.map((group) => (
        <div
          key={group.dateStr}
          className={`sdv-day ${isToday(group.date) ? 'sdv-day-today' : ''} ${
            group.shifts.length === 0 ? 'sdv-day-empty' : ''
          }`}
        >
          {/* Day header */}
          <div className="sdv-day-header">
            <div className="sdv-day-date">
              <span className="sdv-day-number">
                {format(group.date, 'dd')}
              </span>
              <span className="sdv-day-name">
                {format(group.date, 'EEEE', { locale: pt })}
              </span>
            </div>
            {group.shifts.length > 0 && (
              <span className="sdv-day-count">
                {group.shifts.length} turno{group.shifts.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {/* Shifts */}
          {group.shifts.length > 0 ? (
            <div className="sdv-shifts">
              {group.shifts.map((shift) => (
                <button
                  key={shift.id}
                  className="sdv-shift"
                  onClick={() => onShiftClick(shift)}
                  type="button"
                >
                  <div
                    className="sdv-shift-color"
                    style={{
                      backgroundColor:
                        shift.shift_type_color ?? 'var(--color-primary-500)',
                    }}
                  />
                  <div className="sdv-shift-info">
                    <div className="sdv-shift-top">
                      <span className="sdv-shift-type">
                        {shift.shift_type_code ?? shift.shift_type_name ?? 'Turno'}
                      </span>
                      <span className="sdv-shift-time">
                        <Clock size={12} />
                        {formatTime(shift.start_datetime)} — {formatTime(shift.end_datetime)}
                      </span>
                    </div>
                    <div className="sdv-shift-bottom">
                      <span className="sdv-shift-user">
                        <div className="avatar" style={{ width: 22, height: 22, fontSize: '0.55rem' }}>
                          {getInitials(shift.user_name ?? '?')}
                        </div>
                        {shift.user_name}
                      </span>
                      {shift.notes && (
                        <span className="sdv-shift-notes-icon" title="Tem notas">
                          <FileText size={12} />
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="sdv-no-shifts">Sem turnos</div>
          )}
        </div>
      ))}
    </div>
  );
}
