"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import type { Member, Shift, Swap } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { cap, hhmm, longDate, MONTHS, monthCells, shiftMonth, shortDate, today, addDays } from "@/lib/dates";
import { usePostoShifts, useSwaps } from "@/lib/queries";
import { NavBar, LargeTitle } from "@/components/NavBar";
import { Segmented } from "@/components/Segmented";
import { MonthGrid } from "@/components/MonthGrid";
import { Avatar } from "@/components/Avatar";
import { Icon } from "@/components/Icon";
import { Pill } from "@/components/Pill";
import { useSheet } from "@/components/Sheet";
import { MembersSheet } from "@/components/Members";
import { hoursLabel, MemberSheet, RequestSwapSheet, ShiftPill, SwapDetailSheet, swapStatus } from "@/components/sheets";

type Seg = "agora" | "escala" | "trocas";

function GrupoPage() {
  const { membership } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const sheet = useSheet();
  const seg = (params.get("s") as Seg) || "agora";
  const received = useSwaps("received");
  const pending = (received.data ?? []).filter((s) => s.status === "PENDENTE").length;
  return (
    <>
      <NavBar title={membership.groupName} right={<button className="tbtn" onClick={() => sheet.open("Membros", () => <MembersSheet />)}>Membros</button>} />
      <LargeTitle eyebrow={membership.postoName}>{membership.groupName}</LargeTitle>
      <Segmented<Seg>
        label="Secção do grupo"
        value={seg}
        onChange={(v) => router.replace(`/grupo?s=${v}`, { scroll: false })}
        options={[{ value: "agora", label: "Agora" }, { value: "escala", label: "Escala" }, { value: "trocas", label: <>Trocas{pending ? ` (${pending})` : ""}</> }]}
      />
      {seg === "agora" && <Agora />}
      {seg === "escala" && <Escala />}
      {seg === "trocas" && <Trocas />}
    </>
  );
}

export default function Page() {
  return <Suspense><GrupoPage /></Suspense>;
}

function useGroupMembers(): Member[] {
  const { posto, membership } = useApp();
  return posto.groups.find((g) => g.id === membership.groupId)?.members ?? [];
}

function openMember(sheet: ReturnType<typeof useSheet>, m: Member, groupName: string) {
  sheet.open(m.displayName, () => <MemberSheet userId={m.userId} displayName={m.displayName} subtitle={`${groupName}${m.commander ? " · comandante de grupo" : ""}`} />);
}

// ── agora ──

function Agora() {
  const { posto, membership } = useApp();
  const sheet = useSheet();
  const t = today();
  const members = useGroupMembers();
  const shifts = usePostoShifts(posto.id, t, addDays(t, 1), membership.groupId);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(i); }, []);

  const status = (m: Member) => {
    const mine = (shifts.data ?? []).filter((s) => s.userId === m.userId);
    const todays = mine.filter((s) => s.date === t);
    const tomorrow = mine.find((s) => s.date === addDays(t, 1));
    const work = todays.filter((s) => s.kind === "WORK");
    const cur = work.find((s) => Date.parse(s.startsAt) <= now && now < Date.parse(s.endsAt));
    const later = work.find((s) => Date.parse(s.startsAt) > now);
    const absence = todays.find((s) => s.kind === "ABSENCE");
    if (cur) return { cat: "now", shift: cur, txt: `${cur.name} · até às ${hhmm(new Date(cur.endsAt).toTimeString())}`, tomorrow };
    if (later) return { cat: "later", shift: later, txt: `Entra às ${hhmm(later.start)} · ${later.name}`, tomorrow };
    if (absence) return { cat: "abs", shift: absence, txt: absence.name, tomorrow };
    if (work[0]) return { cat: "done", shift: work[0], txt: `Já saiu · ${work[0].name}`, tomorrow };
    return { cat: "off", shift: todays[0], txt: todays[0] ? "De folga" : "Sem serviço hoje", tomorrow };
  };
  const rows = members.map((m) => ({ m, s: status(m) }));
  const cats: [string, string, string][] = [["now", "De serviço agora", "var(--green)"], ["later", "Entra mais tarde", "var(--orange)"], ["done", "Já saiu hoje", "var(--label-3)"], ["off", "De folga", "var(--label-3)"], ["abs", "Ausentes", "var(--tint)"]];
  const count = (c: string) => rows.filter((r) => r.s.cat === c).length;

  return (
    <>
      <div className="section" style={{ marginTop: 18 }}>
        <div className="chips" style={{ padding: 0 }}>
          <div className="stat-chip"><b>{count("now")}</b><span>de serviço</span></div>
          <div className="stat-chip"><b>{count("off")}</b><span>de folga</span></div>
          <div className="stat-chip"><b>{count("abs")}</b><span>ausentes</span></div>
          <div className="stat-chip"><b>{members.length}</b><span>militares</span></div>
        </div>
      </div>
      {cats.map(([cat, title, color]) => {
        const list = rows.filter((r) => r.s.cat === cat);
        if (!list.length) return null;
        return (
          <div className="section" key={cat}>
            <div className="hd"><span><i className="legend-dot" style={{ background: color, borderRadius: "50%" }} />{title}</span></div>
            <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
              {list.map(({ m, s }) => (
                <button key={m.userId} className="row" onClick={() => openMember(sheet, m, membership.groupName)}>
                  <Avatar id={m.userId} name={m.displayName} />
                  <span className="grow">
                    <div className="t">{m.displayName}</div>
                    <div className="s">{s.txt}{s.tomorrow ? ` · amanhã ${s.tomorrow.code}` : ""}</div>
                  </span>
                  {s.shift && <ShiftPill shift={s.shift} size="md" />}
                  <Icon name="chev" className="chev" />
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}

// ── escala em calendário ──

function Escala() {
  const { posto, membership, me } = useApp();
  const sheet = useSheet();
  const t = today();
  const members = useGroupMembers();
  const [[year, month], setYM] = useState<[number, number]>([Number(t.slice(0, 4)), Number(t.slice(5, 7))]);
  const [focus, setFocus] = useState<string | null>(null);
  const cells = monthCells(year, month);
  const shifts = usePostoShifts(posto.id, cells[0]!, cells[cells.length - 1]!, membership.groupId);
  const byKey = useMemo(() => {
    const m = new Map<string, Shift>();
    (shifts.data ?? []).forEach((s) => { const k = `${s.userId}|${s.date}`; if (!m.has(k) || s.kind !== "WORK") m.set(k, m.get(k) ?? s); });
    return m;
  }, [shifts.data]);
  const ordered = [...members].sort((a, b) => (a.userId === me.id ? -1 : b.userId === me.id ? 1 : 0));
  const one = focus ? members.find((m) => m.userId === focus) : undefined;

  const openDay = (d: string) =>
    sheet.open(cap(longDate(d)), () => (
      <div className="section">
        <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
          {ordered.map((m) => {
            const s = byKey.get(`${m.userId}|${d}`);
            const can = m.userId !== me.id && s && s.kind !== "ABSENCE" && d > today();
            return (
              <button key={m.userId} className="row" disabled={!can}
                onClick={() => s && sheet.open("Pedir troca", () => <RequestSwapSheet target={s} targetName={m.displayName} />)}>
                <Avatar id={m.userId} name={m.displayName} />
                <span className="grow"><div className="t" style={m.userId === me.id ? { color: "var(--tint)" } : undefined}>{m.displayName}{m.userId === me.id ? " (eu)" : ""}</div><div className="s">{s ? `${s.name} · ${hoursLabel(s)}` : "Sem serviço"}</div></span>
                {s && <ShiftPill shift={s} size="md" />}
                {can && <Icon name="chev" className="chev" />}
              </button>
            );
          })}
        </div>
      </div>
    ));

  return (
    <>
      <div className="large" style={{ justifyContent: "space-between", alignItems: "center", paddingTop: 14 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ font: "700 22px/1.2 var(--font-d)", letterSpacing: "-.02em" }}>{cap(MONTHS[month - 1]!)}</span><span className="sub num">{year}</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button className="tbtn" aria-label="Mês anterior" style={{ width: 36, justifyContent: "center" }} onClick={() => setYM(shiftMonth(year, month, -1))}><Icon name="chevl" /></button>
          <button className="tbtn" aria-label="Mês seguinte" style={{ width: 36, justifyContent: "center" }} onClick={() => setYM(shiftMonth(year, month, 1))}><Icon name="chev" /></button>
        </div>
      </div>
      <div className="avs" role="tablist" aria-label="Militar">
        <button role="tab" aria-selected={!focus} onClick={() => setFocus(null)}><span className="ico av-all"><Icon name="group" size={18} /></span><span>Todos</span></button>
        {ordered.map((m) => (
          <button key={m.userId} role="tab" aria-selected={focus === m.userId} onClick={() => setFocus(m.userId)}>
            <Avatar id={m.userId} name={m.displayName} size={36} />
            <span>{m.userId === me.id ? "Eu" : m.displayName.split(" ").pop()}</span>
          </button>
        ))}
      </div>
      <div style={{ marginTop: 10 }}>
        <MonthGrid
          year={year}
          month={month}
          onSwipe={(dlt) => setYM(shiftMonth(year, month, dlt))}
          onDay={openDay}
          label={(d) => `${longDate(d)}, ${ordered.filter((m) => byKey.get(`${m.userId}|${d}`)?.kind === "WORK").length} de serviço`}
          renderDay={(d) => {
            if (one) {
              const s = byKey.get(`${one.userId}|${d}`);
              return s ? <ShiftPill shift={s} /> : <span className="pill" style={{ visibility: "hidden" }}>·</span>;
            }
            return (
              <span className="gbars">
                {ordered.map((m) => {
                  const s = byKey.get(`${m.userId}|${d}`);
                  return <i key={m.userId} className={`${!s || s.kind === "OFF" ? "off" : ""} ${s?.kind === "ABSENCE" ? "abs" : ""}`} style={s && s.kind !== "OFF" ? { background: s.color } : undefined} />;
                })}
              </span>
            );
          }}
        />
      </div>
    </>
  );
}

// ── trocas ──

function Trocas() {
  const { me } = useApp();
  const sheet = useSheet();
  const received = useSwaps("received");
  const sent = useSwaps("sent");
  const history = useSwaps("history");
  const card = (s: Swap) => {
    const iAmTarget = s.target.userId === me.id;
    const other = iAmTarget ? s.requester : s.target;
    const give = iAmTarget ? s.targetShift : s.requesterShift;
    const get = iAmTarget ? s.requesterShift : s.targetShift;
    const [label, color] = swapStatus(s, me.id);
    return (
      <button key={s.id} className="row" onClick={() => sheet.open(iAmTarget ? `Pedido de ${other.displayName}` : `Troca com ${other.displayName}`, () => <SwapDetailSheet swap={s} />)}>
        <span className="grow">
          <div className="t">{iAmTarget ? other.displayName : `Para ${other.displayName}`}</div>
          <div className="s">{give && shortDate(give.date)} · <span style={{ color }}>{label}</span></div>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {give && <Pill code={give.code} color={give.color} kind="WORK" size="md" />}
          <Icon name="swap" size={16} style={{ color: "var(--label-2)" }} />
          {get && <Pill code={get.code} color={get.color} kind="WORK" size="md" />}
        </span>
        <Icon name="chev" className="chev" />
      </button>
    );
  };
  const box = (title: string, list: Swap[] | undefined, empty: string) => (
    <div className="section">
      <div className="hd"><span>{title}</span></div>
      {list?.length ? <div className="group">{list.map(card)}</div> : <div className="empty" style={{ background: "var(--card)", borderRadius: 12 }}>{empty}</div>}
    </div>
  );
  return (
    <div style={{ marginTop: -8 }}>
      {box("Recebidas", received.data, "Nada à espera da tua resposta.")}
      {box("Enviadas", sent.data, "Para pedir uma troca, toca no serviço de um camarada.")}
      {!!history.data?.length && box("Histórico", history.data, "")}
    </div>
  );
}
