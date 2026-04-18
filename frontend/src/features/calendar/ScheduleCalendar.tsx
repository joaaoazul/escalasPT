/**
 * ScheduleCalendar — FullCalendar wrapper for shift visualization.
 * Supports month and week views with colored events.
 */

import { useCallback, useMemo, useRef } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import type { EventInput, EventClickArg, DatesSetArg, DateSelectArg, EventDropArg } from '@fullcalendar/core';
import type { EventResizeDoneArg, EventReceiveArg } from '@fullcalendar/interaction';
import type { DropArg } from '@fullcalendar/interaction';
import type { Shift } from '../../types';
import { getShiftColor } from '../../utils/helpers';
import './ScheduleCalendar.css';

interface ScheduleCalendarProps {
  shifts: Shift[];
  isLoading: boolean;
  onEventClick?: (shift: Shift) => void;
  /** Called instead of onEventClick when a grouped event (multiple shifts) is clicked */
  onShiftsClick?: (shifts: Shift[]) => void;
  onDateChange?: (date: Date) => void;
  onEventDrop?: (shift: Shift, newStart: Date, newEnd: Date) => void;
  onEventResize?: (shift: Shift, newStart: Date, newEnd: Date) => void;
  onDateSelect?: (start: Date, end: Date) => void;
  onExternalDrop?: (shiftTypeId: string, date: Date, jsEvent: MouseEvent) => void;
  editable?: boolean;
  selectable?: boolean;
  droppable?: boolean;
  initialDate?: Date;
  height?: string;
  /** Group concurrent same-type shifts into one block (station view) */
  groupByType?: boolean;
}

export function ScheduleCalendar({
  shifts,
  isLoading,
  onEventClick,
  onShiftsClick,
  onDateChange,
  onEventDrop,
  onEventResize,
  onDateSelect,
  onExternalDrop,
  editable = false,
  selectable = false,
  droppable = false,
  initialDate,
  height = 'calc(100vh - 200px)',
  groupByType = false,
}: ScheduleCalendarProps) {
  const calendarRef = useRef<FullCalendar>(null);
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;

  const events: EventInput[] = useMemo(() => {
    // Strip timezone offset so FC treats times as naive local (no UTC→local conversion)
    const stripTZ = (dt: string) => dt.replace(/([+-]\d{2}:\d{2}|Z)$/, '');

    const buildEvent = (shift: Shift, groupShifts: Shift[]): EventInput => {
      const sTime = shift.start_datetime.substring(11, 16);
      const eTime = shift.end_datetime.substring(11, 16);
      const sDate = shift.start_datetime.substring(0, 10);
      const eDate = shift.end_datetime.substring(0, 10);
      const isAllDay = sTime === '00:00' && eTime === '00:00' && sDate === eDate;

      const userCount = groupShifts.length;
      // Show numero_ordem for each assigned user (e.g. "1234·5678"), fallback to initials
      const userDisplay = groupShifts
        .map((s) => s.user_numero_ordem ?? (s.user_name ?? '?').split(' ').slice(0, 2).map((p) => (p[0] ?? '').toUpperCase()).join(''))
        .join(' · ');

      return {
        id: groupShifts.length > 1
          ? `${sDate}__${shift.shift_type_id ?? 'none'}__${shift.status}`
          : shift.id,
        title: shift.shift_type_code ?? shift.shift_type_name ?? 'Turno',
        start: isAllDay ? sDate : stripTZ(shift.start_datetime),
        end: isAllDay ? undefined : stripTZ(shift.end_datetime),
        allDay: isAllDay,
        backgroundColor: getShiftColor(shift.shift_type_color, shift.status),
        borderColor: shift.status === 'draft' ? 'rgba(251, 191, 36, 0.6)' : 'transparent',
        textColor: '#ffffff',
        extendedProps: {
          shift,
          shifts: groupShifts,
          userName: userCount > 1 ? userDisplay : (shift.user_numero_ordem ?? shift.user_name),
          notes: shift.notes,
          status: shift.status,
          shiftTypeName: shift.shift_type_name,
          shiftTypeCode: shift.shift_type_code,
          userCount,
        },
        classNames: [
          `fc-shift-${shift.status}`,
          shift.notes ? 'fc-shift-has-notes' : '',
        ].filter(Boolean),
      };
    };

    if (!groupByType) {
      return shifts.map((s) => buildEvent(s, [s]));
    }

    // Group by date + shift_type_id + status
    const groups = new Map<string, Shift[]>();
    for (const shift of shifts) {
      const key = `${shift.date}__${shift.shift_type_id ?? 'none'}__${shift.status}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(shift);
    }
    return Array.from(groups.values()).map((groupShifts) =>
      buildEvent(groupShifts[0]!, groupShifts),
    );
  }, [shifts, groupByType]);

  const handleEventClick = useCallback(
    (info: EventClickArg) => {
      const groupShifts = info.event.extendedProps['shifts'] as Shift[] | undefined;
      const shift = info.event.extendedProps['shift'] as Shift;
      // If grouped (multiple shifts) and caller supports it, delegate to onShiftsClick
      if (onShiftsClick && groupShifts && groupShifts.length > 1) {
        onShiftsClick(groupShifts);
        return;
      }
      if (onEventClick && shift) {
        onEventClick(shift);
      }
    },
    [onEventClick, onShiftsClick],
  );

  const handleDatesSet = useCallback(
    (arg: DatesSetArg) => {
      if (onDateChange) {
        // Use view.currentStart (nominal first day, e.g. April 1) not arg.start
        // which is the first rendered grid cell (may be in the previous month)
        onDateChange(arg.view.currentStart);
      }
    },
    [onDateChange],
  );

  const handleEventReceive = useCallback((info: EventReceiveArg) => {
    // Always remove the temporary placeholder event — we handle creation ourselves
    info.event.remove();
  }, []);

  const handleDrop = useCallback((info: DropArg) => {
    if (onExternalDrop) {
      const shiftTypeId = (info.draggedEl as HTMLElement).dataset['shiftTypeId'] ?? '';
      onExternalDrop(shiftTypeId, info.date, info.jsEvent as MouseEvent);
    }
  }, [onExternalDrop]);

  const handleEventDrop = useCallback((arg: EventDropArg) => {
    if (onEventDrop) {
      const shift = arg.event.extendedProps['shift'] as Shift;
      if (shift && arg.event.start && arg.event.end) {
        onEventDrop(shift, arg.event.start, arg.event.end);
      }
    }
  }, [onEventDrop]);

  const handleEventResize = useCallback((arg: EventResizeDoneArg) => {
    if (onEventResize) {
      const shift = arg.event.extendedProps['shift'] as Shift;
      if (shift && arg.event.start && arg.event.end) {
        onEventResize(shift, arg.event.start, arg.event.end);
      }
    }
  }, [onEventResize]);

  const handleDateSelect = useCallback((arg: DateSelectArg) => {
    if (onDateSelect) {
      onDateSelect(arg.start, arg.end);
    }
    // clear selection immediately since we handle it via our modal
    arg.view.calendar.unselect();
  }, [onDateSelect]);

  return (
    <div className={`schedule-calendar ${isLoading ? 'calendar-loading' : ''}`}>
      {isLoading && (
        <div className="calendar-loader">
          <div className="spinner" />
          <span>A carregar escala...</span>
        </div>
      )}
      <FullCalendar
        ref={calendarRef}
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        initialView="dayGridMonth"
        initialDate={initialDate}
        headerToolbar={{
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek',
        }}
        buttonText={{
          today: 'Hoje',
          month: 'Mês',
          week: 'Semana',
        }}
        locale="pt"
        firstDay={1}
        height={height}
        editable={editable}
        selectable={selectable}
        droppable={droppable}
        events={events}
        eventClick={handleEventClick}
        datesSet={handleDatesSet}
        eventDrop={handleEventDrop}
        eventResize={handleEventResize}
        select={handleDateSelect}
        eventReceive={handleEventReceive}
        drop={handleDrop}
        eventTimeFormat={{
          hour: '2-digit',
          minute: '2-digit',
          meridiem: false,
          hour12: false,
        }}
        slotLabelFormat={{
          hour: '2-digit',
          minute: '2-digit',
          meridiem: false,
          hour12: false,
        }}
        slotMinTime="00:00:00"
        slotMaxTime="24:00:00"
        allDaySlot={true}
        allDayText="Dia"
        nowIndicator
        dayMaxEvents={isMobile ? 2 : 4}
        moreLinkText={(n) => `+${n} mais`}
        eventDisplay="block"
        eventContent={(arg) => {
          const shift = arg.event.extendedProps['shift'] as Shift | undefined;
          const timeText = arg.timeText;
          const code = (arg.event.extendedProps['shiftTypeCode'] as string | undefined)
            ?? (arg.event.title !== 'Turno' ? arg.event.title : undefined);
          const userName = arg.event.extendedProps['userName'] as string | undefined;
          const status = arg.event.extendedProps['status'] as string;
          const hasNotes = !!shift?.notes;
          const userCount = (arg.event.extendedProps['userCount'] as number) ?? 1;

          return (
            <div className="fc-event-inner">
              <div className="fc-event-row">
                {code && <span className="fc-event-code">{code}</span>}
                {timeText && <span className="fc-event-time">{timeText}</span>}
                {userCount > 1 && (
                  <span className="fc-event-count" title={`${userCount} militares`}>×{userCount}</span>
                )}
              </div>
              {userName && (
                <div className="fc-event-user">{userName}</div>
              )}
              {status === 'draft' && (
                <span className="fc-event-draft-badge">Rascunho</span>
              )}
              {hasNotes && <span className="fc-event-notes-dot" title="Tem notas">●</span>}
            </div>
          );
        }}
      />
    </div>
  );
}
