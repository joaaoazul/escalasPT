/**
 * ShiftTypeLibrary — vertical left-panel with draggable shift type cards.
 * Regular shifts (fixed_slots) get compact single-line rows (dot · code · time).
 * Absences and "outros" get compact chips in a 3-column grid.
 * The panel is collapsible — click the chevron to reclaim horizontal space.
 */

import { useEffect, useRef, useState } from 'react';
import { Draggable } from '@fullcalendar/interaction';
import { Shield, Car, ChevronLeft, ChevronRight } from 'lucide-react';
import { useShiftTypes } from '../../hooks/useShiftTypes';
import type { ShiftType } from '../../types';
import './ShiftTypeLibrary.css';

function computeDuration(st: ShiftType): string {
  if (!st.fixed_slots) return '00:01';
  const parts = (str: string) => str.substring(0, 5).split(':').map(Number) as [number, number];
  const [sh, sm] = parts(st.start_time);
  const [eh, em] = parts(st.end_time);
  let mins = eh * 60 + em - (sh * 60 + sm);
  if (mins <= 0) mins += 24 * 60;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** Full 3-line card: code + icon | time | name */
function ShiftCard({ st, onClick }: { st: ShiftType; onClick?: (st: ShiftType, e: React.MouseEvent) => void }) {
  const Icon = st.code.startsWith('AT') ? Shield : st.code.startsWith('OC') ? Car : null;
  const timeLabel = `${st.start_time.substring(0, 5)} – ${st.end_time.substring(0, 5)}`;
  return (
    <div
      className={`shift-lib-card${onClick ? ' shift-lib-card-clickable' : ''}`}
      draggable
      onDragStart={(e) => e.dataTransfer.setData('application/shift-type-id', st.id)}
      data-shift-type-id={st.id}
      data-code={st.code}
      data-color={st.color}
      data-duration={computeDuration(st)}
      data-is-absence="0"
      style={{ backgroundColor: `${st.color}18`, borderColor: `${st.color}38` }}
      title={st.name}
      onClick={onClick ? (e) => onClick(st, e) : undefined}
    >
      <div className="shift-lib-card-top">
        <span className="shift-lib-card-code" style={{ color: st.color }}>{st.code}</span>
        {Icon && <Icon size={12} style={{ color: st.color, opacity: 0.65, flexShrink: 0 }} />}
      </div>
      <div className="shift-lib-card-time">{timeLabel}</div>
      <div className="shift-lib-card-name">{st.name}</div>
    </div>
  );
}

function ShiftChip({ st, onClick }: { st: ShiftType; onClick?: (st: ShiftType, e: React.MouseEvent) => void }) {
  return (
    <div
      className={`shift-lib-chip${onClick ? ' shift-lib-chip-clickable' : ''}`}
      draggable
      onDragStart={(e) => e.dataTransfer.setData('application/shift-type-id', st.id)}
      data-shift-type-id={st.id}
      data-code={st.code}
      data-color={st.color}
      data-duration={computeDuration(st)}
      data-is-absence={st.is_absence ? '1' : '0'}
      style={{ backgroundColor: `${st.color}18`, borderColor: `${st.color}40` }}
      title={st.name}
      onClick={onClick ? (e) => onClick(st, e) : undefined}
    >
      <span className="shift-lib-chip-code" style={{ color: st.color }}>{st.code}</span>
      <span className="shift-lib-chip-sub">{st.is_absence ? 'Dia int.' : st.name}</span>
    </div>
  );
}

interface ShiftTypeLibraryProps {
  onShiftTypeClick?: (shiftTypeId: string, e: React.MouseEvent) => void;
}

export function ShiftTypeLibrary({ onShiftTypeClick }: ShiftTypeLibraryProps = {}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { data: shiftTypes = [], isLoading } = useShiftTypes();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || shiftTypes.length === 0) return;
    const targets = ['.shift-lib-card', '.shift-lib-chip'];
    const draggable = new Draggable(el, {
      itemSelector: targets.join(', '),
      eventData: (itemEl: HTMLElement) => {
        const shiftTypeId = itemEl.dataset.shiftTypeId ?? '';
        const code = itemEl.dataset.code ?? '';
        const color = itemEl.dataset.color ?? '#6B7280';
        const duration = itemEl.dataset.duration ?? '08:00';
        const isAbsence = itemEl.dataset.isAbsence === '1';
        return {
          title: code,
          duration: isAbsence ? undefined : duration,
          allDay: isAbsence,
          backgroundColor: color,
          borderColor: 'transparent',
          textColor: '#ffffff',
          extendedProps: { shiftTypeId },
        };
      },
    });
    return () => draggable.destroy();
  }, [shiftTypes]);

  const handleClick = onShiftTypeClick
    ? (st: ShiftType, e: React.MouseEvent) => onShiftTypeClick(st.id, e)
    : undefined;

  const active = shiftTypes.filter((st) => st.is_active);
  const regularTypes = active.filter((st) => st.fixed_slots);
  const otherTypes = active.filter((st) => !st.fixed_slots);

  return (
    <aside className={`shift-library${collapsed ? ' lib-collapsed' : ''}`}>

      {/* ── Toggle bar (always visible) ── */}
      <div className="shift-lib-toggle-bar">
        {!collapsed && <span className="shift-library-title">Biblioteca</span>}
        <button
          className="shift-lib-toggle"
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expandir biblioteca' : 'Recolher biblioteca'}
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>
      </div>

      {/* ── Collapsed: color dots only ── */}
      <div className="shift-lib-dots">
        {active.map((st) => (
          <span
            key={st.id}
            className="shift-lib-dot"
            style={{ background: st.color }}
            title={`${st.code} — ${st.name}`}
          />
        ))}
      </div>

      {/* ── Expanded: full list (always mounted so Draggable ref stays valid) ── */}
      <div className="shift-lib-content">
        <div className="shift-library-scroll" ref={containerRef}>
          {isLoading ? (
            <div className="shift-lib-loading"><div className="spinner spinner-sm" /></div>
          ) : (
            <>
              {regularTypes.length > 0 && (
                <div className="shift-lib-group">
                  <span className="shift-lib-group-label">Turnos Regulares</span>
                  <div className="shift-lib-cards">
                    {regularTypes.map((st) => <ShiftCard key={st.id} st={st} onClick={handleClick} />)}
                  </div>
                </div>
              )}
              {otherTypes.length > 0 && (
                <div className="shift-lib-group">
                  <span className="shift-lib-group-label">Ausências &amp; Outros</span>
                  <div className="shift-lib-chip-grid">
                    {otherTypes.map((st) => <ShiftChip key={st.id} st={st} onClick={handleClick} />)}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

    </aside>
  );
}


