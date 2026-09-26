"use client";

import { useMemo, useState } from "react";
import type { Shift } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { cap, hours, MONTHS, monthRange, shiftMonth, today, weekday } from "@/lib/dates";
import { useMyShifts } from "@/lib/queries";
import { NavBar } from "@/components/NavBar";
import { Icon } from "@/components/Icon";
import { Pill } from "@/components/Pill";

const TARGET_HOURS = 160;

/** Minutos noturnos (22:00–07:00, hora local) de um serviço, contados minuto a minuto em tempo real. */
function nightMinutes(s: Shift): number {
  let n = 0;
  for (let t = Date.parse(s.startsAt); t < Date.parse(s.endsAt); t += 60_000) {
    const h = new Date(t).getHours();
    if (h >= 22 || h < 7) n++;
  }
  return n;
}

export default function Horas() {
  const { types } = useApp();
  const t = today();
  const [[year, month], setYM] = useState<[number, number]>([Number(t.slice(0, 4)), Number(t.slice(5, 7))]);
  const range = monthRange(year, month);
  const shifts = useMyShifts(range.from, range.to);
  const yearShifts = useMyShifts(`${year}-01-01`, `${year}-12-31`);

  const st = useMemo(() => {
    const list = shifts.data ?? [];
    const work = list.filter((s) => s.kind === "WORK");
    const minutes = (s: Shift) => (Date.parse(s.endsAt) - Date.parse(s.startsAt)) / 60000;
    const weeks: { label: string; work: number; night: number }[] = [];
    list.forEach((s) => {
      if (s.kind !== "WORK") return;
      const wk = Math.floor((Number(s.date.slice(8)) - 1 + ((weekday(range.from) + 6) % 7)) / 7);
      while (weeks.length <= wk) weeks.push({ label: "", work: 0, night: 0 });
      weeks[wk]!.work += minutes(s);
      weeks[wk]!.night += nightMinutes(s);
    });
    weeks.forEach((w, i) => (w.label = `S${i + 1}`));
    return {
      work: work.reduce((a, s) => a + minutes(s), 0),
      night: work.reduce((a, s) => a + nightMinutes(s), 0),
      weekend: work.filter((s) => [0, 6].includes(weekday(s.date))).reduce((a, s) => a + minutes(s), 0),
      grat: work.filter((s) => s.code === "GRAT").reduce((a, s) => a + minutes(s), 0),
      count: work.length,
      byCode: types.map((ty) => ({ ty, n: list.filter((s) => s.shiftTypeId === ty.id).length })).filter((x) => x.n > 0),
      weeks,
    };
  }, [shifts.data, types, range.from]);

  const fer = (yearShifts.data ?? []).filter((s) => s.code === "FER").length;
  const pct = Math.min(st.work / 60 / TARGET_HOURS, 1);
  const R = 38, C = 2 * Math.PI * R;
  const max = Math.max(...st.weeks.map((w) => w.work), 1);

  return (
    <>
      <NavBar title={`Horas · ${MONTHS[month - 1]}`} />
      <div className="large" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1>Horas</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <button className="tbtn" aria-label="Mês anterior" style={{ width: 32, justifyContent: "center" }} onClick={() => setYM(shiftMonth(year, month, -1))}><Icon name="chevl" /></button>
          <span style={{ fontWeight: 600, minWidth: 86, textAlign: "center", fontSize: 15 }}>{cap(MONTHS[month - 1]!).slice(0, 3)} {year}</span>
          <button className="tbtn" aria-label="Mês seguinte" style={{ width: 32, justifyContent: "center" }} onClick={() => setYM(shiftMonth(year, month, 1))}><Icon name="chev" /></button>
        </div>
      </div>

      <div className="section" style={{ marginTop: 8 }}>
        <div className="ringwrap">
          <svg width="96" height="96" viewBox="0 0 96 96" aria-hidden="true">
            <circle cx="48" cy="48" r={R} fill="none" stroke="var(--fill)" strokeWidth="12" />
            <circle cx="48" cy="48" r={R} fill="none" stroke="var(--tint)" strokeWidth="12" strokeLinecap="round" strokeDasharray={`${C * pct} ${C}`} transform="rotate(-90 48 48)" />
          </svg>
          <div>
            <div className="big">{hours(st.work)}<small> h</small></div>
            <div className="s">{st.count} serviços este mês</div>
          </div>
        </div>
      </div>

      {st.weeks.length > 0 && (
        <div className="section">
          <div className="hd"><span>Por semana</span><span><i className="legend-dot" style={{ background: "var(--tint)" }} />dia <i className="legend-dot" style={{ background: "#2E2C7A", marginLeft: 8 }} />noturno</span></div>
          <div className="bars">
            {st.weeks.map((w) => (
              <div className="b" key={w.label}>
                <small>{hours(w.work)}</small>
                <div className="col" style={{ height: `${Math.max((w.work / max) * 100, 3)}%` }}><i style={{ height: `${w.work ? (w.night / w.work) * 100 : 0}%` }} /></div>
                <small>{w.label}</small>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="section">
        <div className="hd"><span>Detalhe</span></div>
        <div className="group">
          <div className="row"><span className="grow t">Noturno (22h–7h)</span><span className="v">{hours(st.night)} h</span></div>
          <div className="row"><span className="grow t">Fim de semana</span><span className="v">{hours(st.weekend)} h</span></div>
          <div className="row"><span className="grow t">Gratificados</span><span className="v">{hours(st.grat)} h</span></div>
          <div className="row"><span className="grow t">Férias em {year}</span><span className="v">{fer} dias</span></div>
        </div>
      </div>

      {st.byCode.length > 0 && (
        <div className="section">
          <div className="hd"><span>Por tipo</span></div>
          <div className="group">
            {st.byCode.map(({ ty, n }) => (
              <div className="row" key={ty.id}><Pill code={ty.code} color={ty.color} kind={ty.kind} size="md" /><span className="grow t">{ty.name}</span><span className="v">{n}×</span></div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
