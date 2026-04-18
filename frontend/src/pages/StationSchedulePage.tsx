/**
 * StationSchedulePage — full station schedule.
 * Supports two view modes: calendar (FullCalendar) and list (grouped by day).
 * Includes a drag-from-sidebar shift library for comandante / adjunto.
 */

import { useState, useCallback, useEffect } from 'react';
import { startOfMonth, format, getMonth, getYear } from 'date-fns';
import { LayoutList, CalendarDays, Plus, Calendar as CalendarIcon, AlertTriangle, ClipboardList, Download, Maximize2, Minimize2, CalendarRange } from 'lucide-react';
import { useStationSchedule } from '../hooks/useStationSchedule';
import { useAuth } from '../hooks/useAuth';
import { useShiftMutations } from '../hooks/useShiftMutations';
import { ScheduleCalendar } from '../features/calendar/ScheduleCalendar';
import { StationDayView } from '../features/calendar/StationDayView';
import { DailyScheduleView } from '../features/calendar/DailyScheduleView';
import { MonthNavigator } from '../features/calendar/MonthNavigator';
import { ShiftDetailModal } from '../features/calendar/ShiftDetailModal';
import { ShiftGroupDetailPanel } from '../features/calendar/ShiftGroupDetailPanel';
import { ShiftEditorModal } from '../features/calendar/ShiftEditorModal';
import { PublishActionToolbar } from '../features/calendar/PublishActionToolbar';
import { ShiftTypeLibrary } from '../features/calendar/ShiftTypeLibrary';
import { AssignmentPopover } from '../features/calendar/AssignmentPopover';
import { downloadSchedulePdf } from '../api/reports';
import type { AssignmentPayload } from '../features/calendar/AssignmentPopover';
import type { Shift } from '../types';
import './StationSchedulePage.css';

function QuickStats({ shifts }: { shifts: Shift[] }) {
  const today = format(new Date(), 'yyyy-MM-dd');
  const todayCount = shifts.filter((s) => s.date === today && s.status !== 'cancelled').length;
  const draftCount = shifts.filter((s) => s.status === 'draft').length;
  return (
    <div className="quick-stats">
      <div className="quick-stats-header">Resumo Rápido</div>
      <div className="quick-stats-item">
        <CalendarIcon size={14} className="quick-stats-icon" />
        <span>Turnos hoje</span>
        <span className="quick-stats-badge">{todayCount}</span>
      </div>
      <div className="quick-stats-item">
        <AlertTriangle size={14} className="quick-stats-icon quick-stats-warn" />
        <span>Conflitos</span>
        <span className="quick-stats-badge">0</span>
      </div>
      <div className="quick-stats-item">
        <ClipboardList size={14} className="quick-stats-icon quick-stats-pending" />
        <span>Pendentes</span>
        <span className="quick-stats-badge quick-stats-badge-pending">{draftCount}</span>
      </div>
    </div>
  );
}

type ViewMode = 'calendar' | 'list' | 'day';

interface DropState {
  shiftTypeId: string;
  date: Date;
  position: { x: number; y: number };
}

export function StationSchedulePage() {
  const [currentMonth, setCurrentMonth] = useState(() => startOfMonth(new Date()));
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');
  const [selectedDay, setSelectedDay] = useState<Date>(() => new Date());
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
  const [selectedGroupShifts, setSelectedGroupShifts] = useState<Shift[] | null>(null);

  // Editor states (full-form modal — for click-to-create and editing)
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingShift, setEditingShift] = useState<Shift | null>(null);
  const [selectedInitialDate, setSelectedInitialDate] = useState<Date | undefined>(undefined);

  // Drop popover state (quick-assign after drag-from-library)
  const [dropState, setDropState] = useState<DropState | null>(null);

  const { user } = useAuth();
  // adjunto can create/edit but not delete or publish
  const canEdit = user?.role === 'comandante' || user?.role === 'adjunto';
  const isComandante = user?.role === 'comandante';
  const canExportSchedule = canEdit || user?.role === 'secretaria';
  const [exportingSchedule, setExportingSchedule] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // ESC key to exit fullscreen
  useEffect(() => {
    if (!isFullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsFullscreen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isFullscreen]);

  const { data: shifts = [], isLoading } = useStationSchedule(currentMonth);
  const { updateShift, deleteShift, createShift } = useShiftMutations();

  const handleExportSchedule = useCallback(async () => {
    setExportingSchedule(true);
    try {
      await downloadSchedulePdf(getYear(currentMonth), getMonth(currentMonth) + 1);
    } catch {
      // silently fail
    } finally {
      setExportingSchedule(false);
    }
  }, [currentMonth]);

  const handleDateChange = useCallback((date: Date) => {
    setCurrentMonth(startOfMonth(date));
  }, []);

  const handleEventClick = useCallback((shift: Shift) => {
    setSelectedShift(shift);
  }, []);

  const handleGroupClick = useCallback((shifts: Shift[]) => {
    setSelectedGroupShifts(shifts);
  }, []);

  const handleEventDropOrResize = useCallback((shift: Shift, newStart: Date, newEnd: Date) => {
    const dateStr = format(newStart, 'yyyy-MM-dd');
    const startStr = format(newStart, "yyyy-MM-dd'T'HH:mm:ss");
    const endStr = format(newEnd, "yyyy-MM-dd'T'HH:mm:ss");

    updateShift.mutate({
      id: shift.id,
      data: { date: dateStr, start_datetime: startStr, end_datetime: endStr },
    });
  }, [updateShift]);

  const handleDateSelect = useCallback((start: Date) => {
    setSelectedInitialDate(start);
    setEditingShift(null);
    setIsEditorOpen(true);
  }, []);

  // Called when a shift type is dragged from the library and dropped on the calendar
  const handleExternalDrop = useCallback((shiftTypeId: string, date: Date, jsEvent: MouseEvent) => {
    setDropState({
      shiftTypeId,
      date,
      position: { x: jsEvent.clientX + 12, y: jsEvent.clientY + 12 },
    });
  }, []);

  // Confirm from AssignmentPopover — create one shift per selected user
  const handleAssignConfirm = useCallback((payload: AssignmentPayload) => {
    let remaining = payload.userIds.length;
    payload.userIds.forEach((userId) => {
      createShift.mutate(
        {
          user_id: userId,
          shift_type_id: payload.shiftTypeId,
          date: payload.startDatetime.substring(0, 10),
          start_datetime: payload.startDatetime,
          end_datetime: payload.endDatetime,
          notes: payload.notes,
          location: payload.location,
          grat_type: payload.grat_type,
        },
        {
          onSuccess: () => {
            remaining--;
            if (remaining === 0) setDropState(null);
          },
          onError: () => {
            remaining--;
            if (remaining === 0) setDropState(null);
          },
        },
      );
    });
  }, [createShift]);

  const handleCloseDetail = useCallback(() => setSelectedShift(null), []);

  const handleEditShift = useCallback((shift: Shift) => {
    setSelectedShift(null);
    setSelectedGroupShifts(null);
    setEditingShift(shift);
    setSelectedInitialDate(undefined);
    setIsEditorOpen(true);
  }, []);

  const handleDeleteShift = useCallback((shift: Shift) => {
    deleteShift.mutate(shift.id);
    setSelectedShift(null);
  }, [deleteShift]);

  const handleCloseEditor = useCallback(() => {
    setIsEditorOpen(false);
    setEditingShift(null);
    setSelectedInitialDate(undefined);
  }, []);

  // Handle native HTML5 drag-drop on the day view area
  const handleDayViewDragOver = useCallback((e: React.DragEvent) => {
    if (e.dataTransfer.types.includes('application/shift-type-id')) {
      e.preventDefault();
    }
  }, []);

  const handleDayViewDrop = useCallback((e: React.DragEvent) => {
    const shiftTypeId = e.dataTransfer.getData('application/shift-type-id');
    if (!shiftTypeId) return;
    e.preventDefault();
    setDropState({
      shiftTypeId,
      date: selectedDay,
      position: { x: e.clientX + 12, y: e.clientY + 12 },
    });
  }, [selectedDay]);

  const viewToggle = (
    <div className="view-seg">
      <button
        className={`view-seg-btn${viewMode === 'calendar' ? ' view-seg-active' : ''}`}
        onClick={() => setViewMode('calendar')}
        title="Vista calendário"
      >
        <CalendarDays size={14} />
      </button>
      <button
        className={`view-seg-btn${viewMode === 'day' ? ' view-seg-active' : ''}`}
        onClick={() => setViewMode('day')}
        title="Vista diária"
      >
        <CalendarRange size={14} />
      </button>
      <button
        className={`view-seg-btn${viewMode === 'list' ? ' view-seg-active' : ''}`}
        onClick={() => setViewMode('list')}
        title="Vista lista"
      >
        <LayoutList size={14} />
      </button>
      {canEdit && viewMode === 'list' && (
        <button
          className="btn btn-sm btn-primary view-seg-add"
          onClick={() => handleDateSelect(new Date())}
          title="Criar Turno"
        >
          <Plus size={14} />
        </button>
      )}
    </div>
  );

  const fullscreenToggle = (
    <button
      className="btn btn-ghost btn-sm fullscreen-toggle-btn"
      onClick={() => setIsFullscreen((v) => !v)}
      title={isFullscreen ? 'Sair de ecrã inteiro (Esc)' : 'Ecrã inteiro'}
    >
      {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
    </button>
  );

  return (
    <div className={`animate-fade-in station-schedule-page${isFullscreen ? ' station-schedule-fullscreen' : ''}`}>
      {/* Floating exit button in fullscreen */}
      <button
        className="fullscreen-exit-fab"
        onClick={() => setIsFullscreen(false)}
        title="Sair de ecrã inteiro (Esc)"
      >
        <Minimize2 size={16} />
      </button>

      {viewMode === 'list' ? (
        <>
          <MonthNavigator
            currentMonth={currentMonth}
            onMonthChange={setCurrentMonth}
            title="Escala do Posto"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {canExportSchedule && (
                <button
                  className="btn btn-ghost btn-sm swap-download-btn"
                  disabled={exportingSchedule}
                  onClick={handleExportSchedule}
                  title="Exportar escala mensal em PDF"
                >
                  <Download size={14} /> {exportingSchedule ? 'A gerar...' : 'Exportar PDF'}
                </button>
              )}
              {viewToggle}
            </div>
          </MonthNavigator>
          <StationDayView
            shifts={shifts}
            currentMonth={currentMonth}
            onShiftClick={handleEventClick}
            isLoading={isLoading}
          />
        </>
      ) : viewMode === 'day' ? (
        <>
          <div className="station-schedule-header">
            <div>
              <h1 style={{ fontSize: 'var(--font-lg)', fontWeight: 'var(--weight-semibold)', marginBottom: '1px', letterSpacing: '-0.01em' }}>
                Escala Diária
              </h1>
              <p style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                {canEdit
                  ? 'Arraste ou clique num tipo de turno da biblioteca para criar turnos no dia selecionado.'
                  : 'Clique num turno para ver detalhes.'}
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {viewToggle}
            </div>
          </div>
          <div className="station-schedule-body">
            {canEdit && (
              <ShiftTypeLibrary
                onShiftTypeClick={(shiftTypeId, e) => {
                  const rect = (e.target as HTMLElement).getBoundingClientRect();
                  setDropState({
                    shiftTypeId,
                    date: selectedDay,
                    position: { x: rect.right + 12, y: rect.top },
                  });
                }}
              />
            )}
            <div
              className="station-schedule-calendar daily-view-wrapper"
              onDragOver={handleDayViewDragOver}
              onDrop={handleDayViewDrop}
            >
              <DailyScheduleView
                shifts={shifts}
                selectedDate={selectedDay}
                onDateChange={(d) => { setSelectedDay(d); setCurrentMonth(startOfMonth(d)); }}
                onShiftClick={handleEventClick}
                isLoading={isLoading}
              />
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="station-schedule-header">
            <div>
              <h1 style={{ fontSize: 'var(--font-lg)', fontWeight: 'var(--weight-semibold)', marginBottom: '1px', letterSpacing: '-0.01em' }}>
                Escala do Posto
              </h1>
              <p style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                {canEdit
                  ? 'Arraste tipos da biblioteca para criar turnos, ou clique num dia.'
                  : 'Clique num turno para ver detalhes.'}
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {canExportSchedule && (
                <button
                  className="btn btn-ghost btn-sm swap-download-btn"
                  disabled={exportingSchedule}
                  onClick={handleExportSchedule}
                  title="Exportar escala mensal em PDF"
                >
                  <Download size={14} /> {exportingSchedule ? 'A gerar...' : 'Exportar PDF'}
                </button>
              )}
              {fullscreenToggle}
              {viewToggle}
            </div>
          </div>

          <div className="station-schedule-body">
            {canEdit && <ShiftTypeLibrary />}
            <div className="station-schedule-calendar">
              <ScheduleCalendar
                shifts={shifts}
                isLoading={isLoading}
                onEventClick={handleEventClick}
                onDateChange={handleDateChange}
                onEventDrop={handleEventDropOrResize}
                onEventResize={handleEventDropOrResize}
                onDateSelect={handleDateSelect}
                onExternalDrop={handleExternalDrop}
                onShiftsClick={handleGroupClick}
                editable={canEdit}
                selectable={canEdit}
                droppable={canEdit}
                initialDate={currentMonth}
                height={isFullscreen ? 'calc(100vh - 24px)' : 'calc(100vh - 154px)'}
                groupByType
              />
            </div>
            <QuickStats shifts={shifts} />
          </div>
        </>
      )}

      <ShiftDetailModal
        shift={selectedShift}
        onClose={handleCloseDetail}
        canEdit={canEdit}
        onEdit={handleEditShift}
        onDelete={handleDeleteShift}
      />

      {selectedGroupShifts && (
        <ShiftGroupDetailPanel
          shifts={selectedGroupShifts}
          onClose={() => setSelectedGroupShifts(null)}
          currentUser={user}
          canEdit={canEdit}
          onEditShift={handleEditShift}
          onDeleteShift={handleDeleteShift}
        />
      )}

      {isEditorOpen && (
        <ShiftEditorModal
          shift={editingShift}
          initialDate={selectedInitialDate}
          onClose={handleCloseEditor}
        />
      )}

      {dropState && (
        <AssignmentPopover
          shiftTypeId={dropState.shiftTypeId}
          date={dropState.date}
          position={dropState.position}
          onConfirm={handleAssignConfirm}
          onClose={() => setDropState(null)}
          isPending={createShift.isPending}
        />
      )}

      {isComandante && <PublishActionToolbar shifts={shifts} />}
    </div>
  );
}
