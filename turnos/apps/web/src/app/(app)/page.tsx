"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { Shift } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { addDays, cap, hours, longDate, mondayOf, monthRange, relDate, today, WD_LETTER, weekday } from "@/lib/dates";
import { onColor } from "@/lib/color";
import { useMyShifts, usePostoShifts, useSwaps } from "@/lib/queries";
import { NavBar, LargeTitle } from "@/components/NavBar";
import { Bell, PushToggle } from "@/components/Notifications";
import { Avatar } from "@/components/Avatar";
import { Icon } from "@/components/Icon";
import { useSheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { DaySheet, dayTitle, hoursLabel, MemberSheet, ShiftPill, SwapDetailSheet, swapStatus } from "@/components/sheets";
import { useQueryClient } from "@tanstack/react-query";

function useNow(ms = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

export default function Hoje() {
  const { me, membership, posto } = useApp();
  const router = useRouter();
  const sheet = useSheet();
  const qc = useQueryClient();
  const now = useNow();
  const t = today();
  const mine = useMyShifts(addDays(t, -1), addDays(t, 40));
  const group = usePostoShifts(posto.id, t, t, membership.groupId);
  const received = useSwaps("received");
  const month = monthRange(Number(t.slice(0, 4)), Number(t.slice(5, 7)));
  const monthShifts = useMyShifts(month.from, month.to);

  const next = useMemo(() => (mine.data ?? []).find((s) => s.kind === "WORK" && new Date(s.endsAt).getTime() > now), [mine.data, now]);
  const members = posto.groups.find((g) => g.id === membership.groupId)?.members ?? [];
  const nameOf = (id: string) => members.find((m) => m.userId === id)?.displayName ?? "";
  const onDutyToday = (group.data ?? []).filter((s) => s.kind === "WORK" && s.userId !== me.id && new Date(s.endsAt).getTime() > now);
  const worked = (monthShifts.data ?? []).filter((s) => s.kind === "WORK");
  const workedMin = worked.reduce((a, s) => a + (new Date(s.endsAt).getTime() - new Date(s.startsAt).getTime()) / 60000, 0);
  const folgas = (monthShifts.data ?? []).filter((s) => s.kind === "OFF").length;
  const week = Array.from({ length: 7 }, (_, i) => addDays(mondayOf(t), i));
  const byDate = new Map<string, Shift>();
  (mine.data ?? []).forEach((s) => !byDate.has(s.date) && byDate.set(s.date, s));

  const openDay = (d: string) => sheet.open(dayTitle(d), () => <DaySheet date={d} onRequestSwap={(x) => { sheet.close(); router.push(`/posto?dia=${x}`); }} />);

  return (
    <>
      <NavBar
        title="Hoje"
        left={<Bell />}
        right={
          <button className="tbtn" aria-label="Perfil" onClick={() => sheet.open("Perfil", () => <Profile onLogout={async () => {
            await api.POST("/api/v1/auth/logout");
            qc.clear();
            router.replace("/entrar");
          }} />)}>
            <Avatar id={me.id} name={me.fullName} size={30} />
          </button>
        }
      />
      <div className="eyebrow">{cap(longDate(t))}</div>
      <LargeTitle>Hoje</LargeTitle>

      {next ? <Hero shift={next} now={now} onOpen={() => openDay(next.date)} /> : (
        <div className="section" style={{ marginTop: 8 }}><div className="empty" style={{ background: "var(--card)", borderRadius: 12 }}>Sem serviços marcados. <Link href="/calendario">Preencher a escala</Link></div></div>
      )}

      <div className="section">
        <div className="hd"><span>Esta semana</span><Link href="/calendario">Calendário</Link></div>
        <div className="weekstrip">
          {week.map((d) => {
            const s = byDate.get(d);
            return (
              <button key={d} className={d === t ? "today" : ""} onClick={() => openDay(d)} aria-label={`${longDate(d)}${s ? `, ${s.name}` : ""}`}>
                {WD_LETTER[weekday(d)]}
                <b className="num">{Number(d.slice(8))}</b>
                {s ? <ShiftPill shift={s} /> : <span className="pill off" style={{ opacity: 0.4 }}>–</span>}
              </button>
            );
          })}
        </div>
      </div>

      {!!received.data?.length && (
        <div className="section">
          <div className="hd"><span>Pedidos de troca</span></div>
          <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
            {received.data.map((s) => {
              const [label, color] = swapStatus(s, me.id);
              return (
                <button key={s.id} className="row" onClick={() => sheet.open(`Pedido de ${s.requester.displayName}`, () => <SwapDetailSheet swap={s} />)}>
                  <span className="ico" style={{ background: "var(--orange)" }}><Icon name="swap" /></span>
                  <span className="grow">
                    <div className="t">{s.requester.displayName}</div>
                    <div className="s">{s.targetShift && relDate(s.targetShift.date)} · dás {s.targetShift?.code}, recebes {s.requesterShift?.code} · <span style={{ color }}>{label}</span></div>
                  </span>
                  <Icon name="chev" className="chev" />
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="section">
        <div className="hd"><span>{membership.groupName} · de serviço</span><Link href="/grupo">Grupo</Link></div>
        <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
          {onDutyToday.length === 0 && <div className="empty">Ninguém do grupo tem mais serviço hoje.</div>}
          {onDutyToday.map((s) => {
            const live = new Date(s.startsAt).getTime() <= now;
            return (
              <button key={s.id} className="row" onClick={() => sheet.open(nameOf(s.userId), () => <MemberSheet userId={s.userId} displayName={nameOf(s.userId)} subtitle={membership.groupName} />)}>
                <Avatar id={s.userId} name={nameOf(s.userId)} />
                <span className="grow"><div className="t">{nameOf(s.userId)}</div><div className="s">{s.name} · {hoursLabel(s)}</div></span>
                {live && <span className="v" style={{ color: "var(--green)" }}>● agora</span>}
                <ShiftPill shift={s} size="md" />
              </button>
            );
          })}
        </div>
      </div>

      <div className="section"><div className="hd"><span>Este mês</span><Link href="/horas">Horas</Link></div></div>
      <div className="chips">
        <div className="stat-chip"><b>{hours(workedMin)} h</b><span>de serviço</span></div>
        <div className="stat-chip"><b>{worked.length}</b><span>serviços</span></div>
        <div className="stat-chip"><b>{folgas}</b><span>folgas</span></div>
      </div>
    </>
  );
}

function Hero({ shift, now, onOpen }: { shift: Shift; now: number; onOpen: () => void }) {
  const start = new Date(shift.startsAt).getTime(), end = new Date(shift.endsAt).getTime();
  const live = start <= now;
  const ms = Math.max(0, (live ? end : start) - now);
  const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24, m = Math.floor(ms / 6e4) % 60;
  const parts: [number, string][] = [...(d ? ([[d, d === 1 ? "dia" : "dias"]] as [number, string][]) : []), [h, "h"], [m, "min"]];
  return (
    <button className="hero" onClick={onOpen} style={{ "--c": shift.color, "--on": onColor(shift.color), width: "calc(100% - 32px)", textAlign: "left" } as React.CSSProperties}>
      <div className="k">{live ? "A decorrer" : "Próximo serviço"}</div>
      <div>
        <div className="n">{shift.name}</div>
        <div className="when num">{relDate(shift.date)} · {hoursLabel(shift)}</div>
      </div>
      <div className="cd">
        {parts.map(([v, l]) => <div key={l}><b>{v}</b><span>{l}</span></div>)}
        <div style={{ alignSelf: "end", opacity: 0.85, fontSize: 13 }}>{live ? "para terminar" : "para começar"}</div>
      </div>
    </button>
  );
}

const RANKS = ["", "Guarda", "Guarda Principal", "Cabo", "Cabo-Chefe", "Cabo-Mor", "Furriel", "2.º Sargento", "1.º Sargento", "Sargento-Ajudante", "Sargento-Chefe", "Sargento-Mor"];

function ProfileForm() {
  const { me } = useApp();
  const qc = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({ fullName: me.fullName, rank: me.rank ?? "", serviceNumber: me.serviceNumber ?? "" });
  const [busy, setBusy] = useState(false);
  return (
    <form className="section" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      try {
        await unwrap(api.PATCH("/api/v1/me", { body: f }) as never);
        await qc.invalidateQueries();
        toast("Perfil atualizado");
      } catch (err) {
        toast(err instanceof ApiError ? err.message : "Não foi possível guardar", "error");
      } finally {
        setBusy(false);
      }
    }}>
      <div className="hd"><span>Perfil</span></div>
      <div className="group">
        <div className="row"><span className="grow t">Posto</span>
          <select className="field" style={{ width: "auto" }} value={f.rank} onChange={(e) => setF({ ...f, rank: e.target.value })}>
            {RANKS.map((r) => <option key={r} value={r}>{r || "—"}</option>)}
          </select>
        </div>
        <div className="row"><input className="field" aria-label="Nome" value={f.fullName} onChange={(e) => setF({ ...f, fullName: e.target.value })} /></div>
        <div className="row"><input className="field" aria-label="N.º de ordem" placeholder="N.º de ordem" inputMode="numeric" pattern="[0-9]{0,5}" value={f.serviceNumber} onChange={(e) => setF({ ...f, serviceNumber: e.target.value })} /></div>
        <button className="row tint" type="submit" disabled={busy}><span className="grow t">Guardar</span></button>
      </div>
    </form>
  );
}

function Profile({ onLogout }: { onLogout: () => void }) {
  const { me, membership } = useApp();
  return (
    <>
      <div className="section">
        <div className="group">
          <div className="row" style={{ gap: 14, padding: "14px 16px" }}>
            <Avatar id={me.id} name={me.fullName} size={52} />
            <span className="grow"><div className="t" style={{ fontWeight: 600 }}>{[me.rank, me.fullName].filter(Boolean).join(" ")}</div><div className="s">{me.email}</div></span>
          </div>
          <div className="row"><span className="grow t">Posto</span><span className="v">{membership.postoName}</span></div>
          <div className="row"><span className="grow t">Grupo de folgas</span><span className="v">{membership.groupName}{membership.commander ? " · comandante" : ""}</span></div>
          {me.serviceNumber && <div className="row"><span className="grow t">N.º de ordem</span><span className="v">{me.serviceNumber}</span></div>}
        </div>
      </div>
      <ProfileForm />
      <PushToggle />
      <div className="section">
        <div className="group">
          {me.admin && <Link className="row tint" href="/admin"><span className="grow t">Administração</span></Link>}
          <button className="row danger" onClick={onLogout}><span className="grow t">Terminar sessão</span></button>
        </div>
      </div>
    </>
  );
}
