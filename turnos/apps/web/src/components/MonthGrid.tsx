"use client";

import { useRef } from "react";
import { dayNum, longDate, monthCells, today } from "@/lib/dates";

/**
 * Grelha do mês (segunda a domingo). Desliza para os lados para mudar de mês; no modo pincel,
 * tocar ou arrastar sobre os dias chama {@link onPaint} com os dias tocados no fim do gesto.
 */
export function MonthGrid({ year, month, renderDay, onDay, onSwipe, painting, onPaintDay, onPaintEnd, label }: {
  year: number; month: number;
  renderDay: (date: string) => React.ReactNode;
  onDay: (date: string) => void;
  onSwipe: (delta: 1 | -1) => void;
  painting?: boolean;
  onPaintDay?: (date: string) => void;
  onPaintEnd?: () => void;
  label: (date: string) => string;
}) {
  const start = useRef<{ x: number; y: number } | null>(null);
  const swiped = useRef(false);
  const pre = `${year}-${String(month).padStart(2, "0")}`;
  const t = today();

  const dayAt = (x: number, y: number) => (document.elementFromPoint(x, y) as HTMLElement | null)?.closest<HTMLElement>("[data-date]")?.dataset.date;

  return (
    <>
      <div className="wk" aria-hidden="true"><span>S</span><span>T</span><span>Q</span><span>Q</span><span>S</span><span>S</span><span>D</span></div>
      <div
        className={`monthgrid ${painting ? "painting" : ""}`}
        role="grid"
        onPointerDown={(e) => {
          start.current = { x: e.clientX, y: e.clientY };
          if (painting) {
            (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
            const d = dayAt(e.clientX, e.clientY);
            if (d) onPaintDay?.(d);
          }
        }}
        onPointerMove={(e) => {
          if (!painting || !start.current) return;
          const d = dayAt(e.clientX, e.clientY);
          if (d) onPaintDay?.(d);
        }}
        onPointerUp={(e) => {
          if (!start.current) return;
          const dx = e.clientX - start.current.x, dy = e.clientY - start.current.y;
          start.current = null;
          if (painting) {
            swiped.current = true;
            onPaintEnd?.();
          } else if (Math.abs(dx) > 60 && Math.abs(dy) < 45) {
            swiped.current = true;
            onSwipe(dx < 0 ? 1 : -1);
          }
        }}
        onPointerCancel={() => { start.current = null; if (painting) onPaintEnd?.(); }}
      >
        {monthCells(year, month).map((d) => (
          <button
            key={d}
            data-date={d}
            role="gridcell"
            aria-label={label(d)}
            className={`day ${d.startsWith(pre) ? "" : "out"} ${d === t ? "today" : ""}`}
            onClick={() => {
              if (swiped.current) { swiped.current = false; return; }
              if (!painting) onDay(d);
            }}
          >
            <span className="dn">{dayNum(d)}</span>
            {renderDay(d)}
          </button>
        ))}
      </div>
    </>
  );
}

export const dayLabel = (d: string, what: string) => `${longDate(d)}, ${what}`;
