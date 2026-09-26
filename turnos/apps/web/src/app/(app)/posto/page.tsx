"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";
import type { Member, Shift } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { addDays, cap, dayNum, longDate, mondayOf, MONTHS, monthIdx, relDate, today, WD_LETTER, weekday } from "@/lib/dates";
import { usePostoShifts } from "@/lib/queries";
import { NavBar, LargeTitle } from "@/components/NavBar";
import { Segmented } from "@/components/Segmented";
import { Avatar } from "@/components/Avatar";
import { Icon } from "@/components/Icon";
import { useSheet } from "@/components/Sheet";
import { hoursLabel, MemberSheet, RequestSwapSheet, ShiftPill } from "@/components/sheets";

type Person = Member & { group: string };

function PostoPage() {
  const { posto, types, me } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const sheet = useSheet();
  const t = today();
  const view = params.get("v") === "semana" ? "semana" : "dia";
  const day = params.get("dia") ?? t;
  const week = params.get("semana") ?? mondayOf(t);
  const nav = (q: Record<string, string>) => router.replace(`/posto?${new URLSearchParams({ v: view, dia: day, semana: week, ...q })}`, { scroll: false });

  const people = useMemo<Person[]>(() => posto.groups.flatMap((g) => g.members.map((m) => ({ ...m, group: g.name }))), [posto]);
  const person = (id: string) => people.find((p) => p.userId === id);
  const from = view === "dia" ? day : week;
  const to = view === "dia" ? day : addDays(week, 6);
  const shifts = usePostoShifts(posto.id, from, to);

  const openShift = (s: Shift) => {
    const p = person(s.userId);
    if (!p) return;
    if (p.userId !== me.id && s.kind !== "ABSENCE" && s.date > t) {
      sheet.open("Pedir troca", () => <RequestSwapSheet target={s} targetName={p.displayName} />);
    } else {
      sheet.open(p.displayName, () => <MemberSheet userId={p.userId} displayName={p.displayName} subtitle={p.group} />);
    }
  };

  return (
    <>
      <NavBar title="Escala do posto" />
      <LargeTitle eyebrow={posto.name}>Escala do posto</LargeTitle>
      <Segmented label="Vista" value={view} onChange={(v) => nav({ v })} options={[{ value: "dia", label: "Dia" }, { value: "semana", label: "Semana" }]} />

      {view === "dia" ? (
        <>
          <div className="section" style={{ marginTop: 14 }}>
            <div className="group">
              <div className="row">
                <button className="tbtn" aria-label="Dia anterior" style={{ width: 32 }} onClick={() => nav({ dia: addDays(day, -1) })}><Icon name="chevl" /></button>
                <span className="grow" style={{ textAlign: "center", fontWeight: 600 }}>{relDate(day) === "Hoje" || relDate(day) === "Amanhã" ? `${relDate(day)}, ${dayNum(day)} de ${MONTHS[monthIdx(day)]}` : cap(longDate(day))}</span>
                <button className="tbtn" aria-label="Dia seguinte" style={{ width: 32, justifyContent: "flex-end" }} onClick={() => nav({ dia: addDays(day, 1) })}><Icon name="chev" /></button>
              </div>
            </div>
          </div>
          {types.filter((ty) => ty.kind === "WORK").map((ty) => {
            const list = (shifts.data ?? []).filter((s) => s.shiftTypeId === ty.id);
            if (!list.length) return null;
            return (
              <div className="section" key={ty.id}>
                <div className="hd">
                  <span style={{ display: "flex", alignItems: "center", gap: 8, textTransform: "none", letterSpacing: 0, fontSize: 15, color: "var(--label)" }}>
                    <ShiftPill shift={{ code: ty.code, color: ty.color, kind: ty.kind }} />{ty.name}
                  </span>
                  {ty.startTime && <span className="num">{hoursLabel({ start: ty.startTime, durationMinutes: ty.durationMinutes })}</span>}
                </div>
                <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
                  {list.map((s) => <PersonRow key={s.id} p={person(s.userId)} extra={ty.startTime ? undefined : hoursLabel(s)} onClick={() => openShift(s)} me={me.id} />)}
                </div>
              </div>
            );
          })}
          {(["OFF", "ABSENCE"] as const).map((kind) => {
            const list = (shifts.data ?? []).filter((s) => s.kind === kind);
            if (!list.length) return null;
            return (
              <div className="section" key={kind}>
                <div className="hd"><span>{kind === "OFF" ? "Folga" : "Ausentes"}</span><span>{list.length}</span></div>
                <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
                  {list.map((s) => <PersonRow key={s.id} p={person(s.userId)} extra={kind === "ABSENCE" ? s.name : undefined} onClick={() => openShift(s)} me={me.id} pill={s} />)}
                </div>
              </div>
            );
          })}
          {!shifts.isLoading && !shifts.data?.length && <div className="section"><div className="empty" style={{ background: "var(--card)", borderRadius: 12 }}>Ainda ninguém marcou serviço para este dia.</div></div>}
        </>
      ) : (
        <>
          <div className="section" style={{ marginTop: 18 }}>
            <div className="hd">
              <span>{dayNum(week)} {MONTHS[monthIdx(week)]!.slice(0, 3)} – {dayNum(addDays(week, 6))} {MONTHS[monthIdx(addDays(week, 6))]!.slice(0, 3)}</span>
              <span style={{ display: "flex", gap: 14 }}>
                <button aria-label="Semana anterior" onClick={() => nav({ semana: addDays(week, -7) })}><Icon name="chevl" size={18} /></button>
                <button aria-label="Semana seguinte" onClick={() => nav({ semana: addDays(week, 7) })}><Icon name="chev" size={18} /></button>
              </span>
            </div>
          </div>
          <WeekTable week={week} shifts={shifts.data ?? []} onShift={openShift} />
        </>
      )}
    </>
  );
}

function PersonRow({ p, extra, onClick, me, pill }: { p?: Person; extra?: string; onClick: () => void; me: string; pill?: Shift }) {
  if (!p) return null;
  return (
    <button className="row" onClick={onClick}>
      <Avatar id={p.userId} name={p.displayName} />
      <span className="grow">
        <div className="t" style={p.userId === me ? { color: "var(--tint)" } : undefined}>{p.displayName}{p.userId === me ? " (eu)" : ""}</div>
        <div className="s">{p.group}{extra ? ` · ${extra}` : ""}</div>
      </span>
      {pill && <ShiftPill shift={pill} size="md" />}
      <Icon name="chev" className="chev" />
    </button>
  );
}

function WeekTable({ week, shifts, onShift }: { week: string; shifts: Shift[]; onShift: (s: Shift) => void }) {
  const { posto, me } = useApp();
  const t = today();
  const days = Array.from({ length: 7 }, (_, i) => addDays(week, i));
  const at = new Map<string, Shift>();
  shifts.forEach((s) => { const k = `${s.userId}|${s.date}`; if (!at.has(k)) at.set(k, s); });
  const counts = days.map((d) => shifts.filter((s) => s.date === d && s.kind === "WORK").length);
  return (
    <div className="roster-wrap">
      <table className="roster" style={{ minWidth: "100%" }}>
        <thead>
          <tr>
            <th style={{ position: "sticky", left: 0, background: "var(--card)", zIndex: 2 }} />
            {days.map((d) => <th key={d} className={d === t ? "today" : ""}>{WD_LETTER[weekday(d)]}<b className="num">{dayNum(d)}</b></th>)}
          </tr>
        </thead>
        <tbody>
          {posto.groups.map((g) => [
            <tr key={g.id}><th colSpan={8} className="grp-h">{g.name}</th></tr>,
            ...g.members.map((m) => (
              <tr key={m.userId} className={m.userId === me.id ? "me" : ""}>
                <th>{m.displayName.split(" ").pop()}<small>{m.rank ?? ""}</small></th>
                {days.map((d) => {
                  const s = at.get(`${m.userId}|${d}`);
                  return (
                    <td key={d}>
                      {s ? <button aria-label={`${m.displayName}, ${s.name}`} onClick={() => onShift(s)}><ShiftPill shift={s} /></button> : <span className="free">·</span>}
                    </td>
                  );
                })}
              </tr>
            )),
          ])}
        </tbody>
        <tfoot><tr><th>De serviço</th>{counts.map((n, i) => <td key={i}>{n}</td>)}</tr></tfoot>
      </table>
    </div>
  );
}

export default function Page() {
  return <Suspense><PostoPage /></Suspense>;
}
