/**
 * SchedulePage — personal schedule with FullCalendar.
 * Militar: read-only published shifts.
 * Comandante: sees draft + published shifts.
 */

import { useState, useCallback } from 'react';
import { startOfMonth } from 'date-fns';
import { usePersonalSchedule } from '../hooks/usePersonalSchedule';
import { useAuth } from '../hooks/useAuth';
import { ScheduleCalendar } from '../features/calendar/ScheduleCalendar';
import { ShiftDetailModal } from '../features/calendar/ShiftDetailModal';
import type { Shift } from '../types';

export function SchedulePage() {
  const [currentMonth, setCurrentMonth] = useState(() => startOfMonth(new Date()));
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
  const { user } = useAuth();

  const { data: shifts = [], isLoading } = usePersonalSchedule(currentMonth);

  const handleDateChange = useCallback((date: Date) => {
    setCurrentMonth(startOfMonth(date));
  }, []);

  const handleEventClick = useCallback((shift: Shift) => {
    setSelectedShift(shift);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedShift(null);
  }, []);

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{
          fontSize: 'var(--font-2xl)',
          fontWeight: 'var(--weight-bold)',
          marginBottom: 'var(--space-1)',
        }}>
          Minha Escala
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-sm)' }}>
          Visualize os seus turnos atribuídos. Clique num turno para ver detalhes.
        </p>
      </div>

      <ScheduleCalendar
        shifts={shifts}
        isLoading={isLoading}
        onEventClick={handleEventClick}
        onDateChange={handleDateChange}
        initialDate={currentMonth}
      />

      <ShiftDetailModal
        shift={selectedShift}
        onClose={handleCloseDetail}
        canRequestSwap={user?.role === 'militar'}
      />
    </div>
  );
}
