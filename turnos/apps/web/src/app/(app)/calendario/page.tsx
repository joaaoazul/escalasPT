"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ApiError } from "@/lib/api/client";
import type { Shift } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { cap, hours, longDate, MONTHS, monthCells, relDate, shiftMonth, today } from "@/lib/dates";
import { useMyShifts, usePaint } from "@/lib/queries";
import { NavBar } from "@/components/NavBar";
import { MonthGrid } from "@/components/MonthGrid";
import { Pill } from "@/components/Pill";
import { Icon } from "@/components/Icon";
import { useSheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { DaySheet, dayTitle, hoursLabel, ShiftPill } from "@/components/sheets";

type Stroke = { typeId: string | null; before: Map<string, string | null> };

export default function Calendario() {
  const { types } = useApp();
  const router = useRouter();
  const sheet = useSheet();
  const toast = useToast();
  const t = today();
  const [[year, month], setYM] = useState<[number, number]>([Number(t.slice(0, 4)), Number(t.slice(5, 7))]);
  const cells = monthCells(year, month);
  const shifts = useMyShifts(cells[0]!, cells[cells.length - 1]!);
  const paint = usePaint();

  const [painting, setPainting] = useState(false);
  const [brush, setBrush] = useState<string | null>(() => types.find((x) => x.code === "AT2")?.id ?? types[0]?.id ?? null);
  const [stroke, setStroke] = useState<Map<string, string | null>>(new Map());
  const [undo, setUndo] = useState<Stroke[]>([]);

  const byDate = useMemo(() => {
    const m = new Map<string, Shift[]>();
    (shifts.data ?? []).forEach((s) => m.set(s.date, [...(m.get(s.date) ?? []), s]));
    return m;
  }, [shifts.data]);
  const paintable = types.filter((x) => x.allDay || x.startTime);
  const typeOf = (id: string | null) => (id ? types.find((x) => x.id === id) : undefined);

  const openDay = (d: string) =>
    sheet.open(dayTitle(d), () => <DaySheet date={d} onRequestSwap={(x) => { sheet.close(); router.push(`/posto?dia=${x}`); }} />);

  const go = (delta: 1 | -1) => setYM(shiftMonth(year, month, delta));

  /** Aplica o traço: agrupa os dias pelo que lá estava antes (para o desfazer) e envia um só pedido. */
  const apply = (dates: string[], typeId: string | null, record: boolean) => {
    if (!dates.length) return;
    const before = new Map(dates.map((d) => [d, byDate.get(d)?.[0]?.shiftTypeId ?? null]));
    paint.mutate(
      { shiftTypeId: typeId, dates },
      {
        onSuccess: (r) => {
          if (record) setUndo((u) => [...u.slice(-19), { typeId, before }]);
          if (r.warnings[0]) toast(r.warnings[0].message);
        },
        onError: (e) => toast(e instanceof ApiError ? e.message : "Não foi possível guardar", "error"),
        onSettled: () => setStroke(new Map()),
      },
    );
  };

  const undoLast = () => {
    const last = undo[undo.length - 1];
    if (!last) return;
    setUndo(undo.slice(0, -1));
    const groups = new Map<string | null, string[]>();
    last.before.forEach((typeId, d) => groups.set(typeId, [...(groups.get(typeId) ?? []), d]));
    groups.forEach((dates, typeId) => apply(dates, typeId, false));
  };

  const pre = `${year}-${String(month).padStart(2, "0")}`;
  const monthShifts = (shifts.data ?? []).filter((s) => s.date.startsWith(pre));
  const workMin = monthShifts.filter((s) => s.kind === "WORK").reduce((a, s) => a + (Date.parse(s.endsAt) - Date.parse(s.startsAt)) / 60000, 0);
  const upcoming = (shifts.data ?? []).filter((s) => s.kind === "WORK" && s.date >= (pre === t.slice(0, 7) ? t : `${pre}-01`)).slice(0, 5);

  return (
    <>
      <NavBar
        title={`${cap(MONTHS[month - 1]!)} ${year}`}
        right={
          painting ? (
            <>
              <button className="tbtn" aria-label="Desfazer" disabled={!undo.length || paint.isPending} onClick={undoLast}><Icon name="undo" /></button>
              <button className="tbtn bold" onClick={() => setPainting(false)}>OK</button>
            </>
          ) : (
            <>
              <button className="tbtn" onClick={() => setYM([Number(t.slice(0, 4)), Number(t.slice(5, 7))])}>Hoje</button>
              <button className="tbtn" aria-label="Pintar dias" onClick={() => setPainting(true)}><Icon name="brush" /></button>
            </>
          )
        }
      />
      <div className="large" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}><h1>{cap(MONTHS[month - 1]!)}</h1><span className="sub num">{year}</span></div>
        <div style={{ display: "flex", gap: 4 }}>
          <button className="tbtn" aria-label="Mês anterior" style={{ width: 36, justifyContent: "center" }} onClick={() => go(-1)}><Icon name="chevl" /></button>
          <button className="tbtn" aria-label="Mês seguinte" style={{ width: 36, justifyContent: "center" }} onClick={() => go(1)}><Icon name="chev" /></button>
        </div>
      </div>

      <MonthGrid
        year={year}
        month={month}
        painting={painting}
        onSwipe={go}
        onDay={openDay}
        label={(d) => `${longDate(d)}, ${(byDate.get(d) ?? []).map((s) => s.name).join(", ") || "sem serviço"}`}
        onPaintDay={(d) => !stroke.has(d) && setStroke(new Map(stroke).set(d, brush))}
        onPaintEnd={() => apply([...stroke.keys()], brush, true)}
        renderDay={(d) => {
          if (stroke.has(d)) {
            const ty = typeOf(stroke.get(d) ?? null);
            return ty ? <Pill code={ty.code} color={ty.color} kind={ty.kind} /> : <span className="pill" style={{ visibility: "hidden" }}>·</span>;
          }
          const list = byDate.get(d) ?? [];
          return (
            <>
              {list[0] ? <ShiftPill shift={list[0]} /> : <span className="pill" style={{ visibility: "hidden" }}>·</span>}
              {list.length > 1 && <span className="dots"><i style={{ background: list[1]!.color }} /></span>}
            </>
          );
        }}
      />

      {!painting && (
        <>
          <div className="section" style={{ marginTop: 18 }}>
            <div className="chips" style={{ padding: 0 }}>
              <div className="stat-chip"><b>{hours(workMin)} h</b><span>{monthShifts.filter((s) => s.kind === "WORK").length} serviços</span></div>
              <div className="stat-chip"><b>{monthShifts.filter((s) => s.kind === "OFF").length}</b><span>folgas</span></div>
              <div className="stat-chip"><b>{monthShifts.filter((s) => s.kind === "ABSENCE").length}</b><span>ausências</span></div>
            </div>
          </div>
          {upcoming.length > 0 && (
            <div className="section">
              <div className="hd"><span>Próximos serviços</span></div>
              <div className="group" style={{ "--inset": "32px" } as React.CSSProperties}>
                {upcoming.map((s) => (
                  <button key={s.id} className="row" onClick={() => openDay(s.date)}>
                    <span className="bar-l" style={{ background: s.color }} />
                    <span className="grow"><div className="t">{s.name}</div><div className="s">{relDate(s.date)}</div></span>
                    <span className="v">{hoursLabel(s)}</span>
                    <Icon name="chev" className="chev" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div className={`paintbar ${painting ? "" : "closed"}`} aria-hidden={!painting}>
        <div className="paint-hint">{paint.isPending ? "A guardar…" : brush ? `A pintar: ${typeOf(brush)?.name}` : "A limpar dias"}</div>
        <div className="brushes">
          {paintable.map((ty) => (
            <button key={ty.id} className="brush" aria-pressed={brush === ty.id} onClick={() => setBrush(ty.id)}>
              <Pill code={ty.code} color={ty.color} kind={ty.kind} />
              <span>{ty.code}</span>
            </button>
          ))}
          <button className="brush" aria-pressed={brush === null} onClick={() => setBrush(null)}>
            <span className="pill clear">✕</span>
            <span>Limpar</span>
          </button>
        </div>
      </div>
      {painting && <div style={{ height: 120 }} />}
    </>
  );
}
