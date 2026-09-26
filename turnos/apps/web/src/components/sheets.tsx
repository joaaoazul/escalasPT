"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api/client";
import { ACTIVE, type Shift, type ShiftRef, type Swap } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { addDays, cap, endTime, hhmm, longDate, shortDate, stamp, today } from "@/lib/dates";
import { useAddShift, useDeleteShift, useMyShifts, usePaint, useRequestSwap, useSwapAction, useUserShifts } from "@/lib/queries";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { Pill } from "./Pill";
import { useSheet } from "./Sheet";
import { useToast } from "./Toast";

// ── auxiliares de apresentação ──

export function ShiftPill({ shift, size, pending }: { shift: Pick<Shift, "code" | "color" | "kind">; size?: "md" | "lg"; pending?: boolean }) {
  return <Pill code={shift.code} color={shift.color} kind={shift.kind} size={size} pending={pending} />;
}

export function hoursLabel(s: { start: string | null; durationMinutes: number | null }): string {
  return s.start ? `${hhmm(s.start)}–${endTime(s.start, s.durationMinutes).replace(/^00:00$/, "24:00")}` : "Dia inteiro";
}

function useKindOf() {
  const { types } = useApp();
  return (code: string) => types.find((t) => t.code === code)?.kind ?? "WORK";
}

function WarningBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="warn">
      <Icon name="warn" />
      <div>{children}</div>
    </div>
  );
}

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : "Sem ligação ao servidor");

// ── ficha de um camarada ──

export function MemberSheet({ userId, displayName, subtitle }: { userId: string; displayName: string; subtitle: string }) {
  const { me } = useApp();
  const sheet = useSheet();
  const from = today();
  const shifts = useUserShifts(userId, from, addDays(from, 13));
  const days = Array.from({ length: 14 }, (_, i) => addDays(from, i));
  const byDate = new Map<string, Shift>();
  (shifts.data ?? []).forEach((s) => !byDate.has(s.date) && byDate.set(s.date, s));
  const mine = userId === me.id;
  return (
    <>
      <div className="section">
        <div className="group">
          <div className="row" style={{ gap: 14, padding: "14px 16px" }}>
            <Avatar id={userId} name={displayName} size={52} />
            <span className="grow">
              <div className="t" style={{ fontWeight: 600 }}>{displayName}</div>
              <div className="s">{subtitle}</div>
            </span>
          </div>
        </div>
      </div>
      <div className="section">
        <div className="hd"><span>Próximos 14 dias</span></div>
        <div className="weekstrip" style={{ rowGap: 12 }}>
          {days.map((d) => {
            const s = byDate.get(d);
            const can = !mine && s && s.date > today() && s.kind !== "ABSENCE";
            return (
              <button
                key={d}
                className={d === today() ? "today" : ""}
                disabled={!can}
                aria-label={`${longDate(d)}${s ? `, ${s.name}` : ""}`}
                onClick={() => s && sheet.open("Pedir troca", () => <RequestSwapSheet target={s} targetName={displayName} />)}
              >
                {"DSTQQSS"[new Date(`${d}T12:00:00Z`).getUTCDay()]}
                <b className="num">{Number(d.slice(8))}</b>
                {s ? <ShiftPill shift={s} /> : <span className="pill off" style={{ opacity: 0.4 }}>–</span>}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ── pedir troca ──

export function RequestSwapSheet({ target, targetName }: { target: Shift; targetName: string }) {
  const sheet = useSheet();
  const toast = useToast();
  const { typeById } = useApp();
  const from = addDays(today(), 1);
  const mine = useMyShifts(from, addDays(from, 60));
  const request = useRequestSwap();
  const [message, setMessage] = useState("");
  const candidates = (mine.data ?? []).filter((s) => typeById.get(s.shiftTypeId)?.swappable);
  const sameDay = candidates.find((s) => s.date === target.date);
  const [chosen, setChosen] = useState<string | null>(null);
  const give = candidates.find((s) => s.id === chosen) ?? sameDay ?? candidates[0];

  if (mine.isLoading) return <div className="empty"><div className="spinner" style={{ margin: "0 auto" }} /></div>;
  if (!give) return <div className="section"><WarningBox>Não tens serviços futuros que possas trocar.</WarningBox></div>;

  return (
    <>
      <SwapLine give={give} get={target} otherName={targetName} />
      {give.date !== target.date && (
        <div className="section" style={{ marginTop: 12 }}>
          <WarningBox>O teu serviço é de {shortDate(give.date)}; o do camarada é de {shortDate(target.date)}.</WarningBox>
        </div>
      )}
      <div className="section">
        <div className="hd"><span>O teu serviço</span></div>
        <div className="group">
          <div className="row">
            <select id="give-shift" className="field" style={{ textAlign: "left", color: "var(--label)" }} value={give.id} onChange={(e) => setChosen(e.target.value)}>
              {candidates.map((s) => (
                <option key={s.id} value={s.id}>{`${shortDate(s.date)} · ${s.code} ${s.kind === "OFF" ? "" : hoursLabel(s)}`}</option>
              ))}
            </select>
          </div>
          <div className="row">
            <input id="swap-message" className="field" placeholder="Mensagem" maxLength={280} value={message} onChange={(e) => setMessage(e.target.value)} />
          </div>
        </div>
      </div>
      <div className="section" style={{ marginTop: 16 }}>
        <button
          className="btn primary"
          style={{ width: "100%" }}
          disabled={request.isPending}
          onClick={() =>
            request.mutate(
              { shiftId: give.id, targetShiftId: target.id, message: message.trim() || undefined },
              {
                onSuccess: (r) => {
                  toast(r.warnings?.[0] ? `Pedido enviado · ${r.warnings[0].message}` : `Pedido enviado a ${targetName}`);
                  sheet.close();
                },
                onError: (e) => toast(errorText(e), "error"),
              },
            )
          }
        >
          Enviar pedido
        </button>
      </div>
    </>
  );
}

function SwapLine({ give, get, otherName }: {
  give: Pick<Shift, "code" | "color" | "name" | "start" | "durationMinutes" | "date"> & { kind?: string };
  get: Pick<Shift, "code" | "color" | "name" | "start" | "durationMinutes" | "date"> & { kind?: string };
  otherName: string;
}) {
  const kindOf = useKindOf();
  const side = (label: string, s: typeof give) => (
    <div className="sd">
      <span>{label}</span>
      <Pill code={s.code} color={s.color} kind={s.kind ?? kindOf(s.code)} size="lg" />
      <b>{s.name}</b>
      <span className="num">{shortDate(s.date)} · {hoursLabel(s)}</span>
    </div>
  );
  return (
    <div className="section">
      <div className="group" style={{ padding: "18px 12px" }}>
        <div className="swapline">
          {side("Dás", give)}
          <Icon name="swap" size={26} style={{ color: "var(--tint)" }} />
          {side(`Recebes de ${otherName}`, get)}
        </div>
      </div>
    </div>
  );
}

// ── detalhe de uma troca ──

const STATUS: Record<string, [string, string]> = {
  PENDENTE: ["Aguarda resposta", "var(--orange)"],
  EM_ESPERA: ["Pediu para aguardar", "var(--tint)"],
  ACEITE: ["Aceite · documento emitido", "var(--green)"],
  RECUSADA: ["Recusada", "var(--red)"],
  CANCELADA: ["Cancelada", "var(--label-2)"],
  EXPIRADA: ["Expirou na véspera", "var(--label-2)"],
};

export function swapStatus(s: Swap, meId: string): [string, string] {
  if (s.status === "PENDENTE" && s.target.userId === meId) return ["Aguarda a tua resposta", "var(--orange)"];
  if (s.status === "EM_ESPERA" && s.target.userId === meId) return ["Pediste para aguardar", "var(--tint)"];
  return STATUS[s.status] ?? [s.status, "var(--label-2)"];
}

const HOLD = ["Deixa-me ver em casa, já te digo.", "Respondo-te amanhã de manhã.", "Estou de serviço, vejo quando sair."];
const DECLINE = ["Já tenho compromisso nesse dia.", "Fico com poucas horas de descanso.", "Não me dá jeito, desculpa."];

export function SwapDetailSheet({ swap }: { swap: Swap }) {
  const { me } = useApp();
  const sheet = useSheet();
  const toast = useToast();
  const action = useSwapAction();
  const [mode, setMode] = useState<null | "hold" | "decline">(null);
  const iAmTarget = swap.target.userId === me.id;
  const other = iAmTarget ? swap.requester : swap.target;
  const give = iAmTarget ? swap.targetShift : swap.requesterShift;
  const get = iAmTarget ? swap.requesterShift : swap.targetShift;
  const active = (ACTIVE as string[]).includes(swap.status);

  const run = (a: "accept" | "hold" | "decline" | "cancel", message?: string, ok?: string) =>
    action.mutate(
      { id: swap.id, action: a, message },
      {
        onSuccess: (s) => {
          toast(ok ?? "Feito");
          if (a === "accept") sheet.open("Troca aceite", () => <SwapDetailSheet swap={s} />);
          else sheet.close();
        },
        onError: (e) => toast(errorText(e), "error"),
      },
    );

  const events: [string, string][] = [[swap.createdAt, `${iAmTarget ? other.displayName : "Tu"} ${iAmTarget ? "pediu" : "pediste"} a troca`]];
  if (swap.heldAt) events.push([swap.heldAt, `${iAmTarget ? "Pediste" : `${other.displayName} pediu`} para aguardar${swap.holdMessage ? `: “${swap.holdMessage}”` : ""}`]);
  if (swap.respondedAt && swap.status !== "EM_ESPERA") {
    const label: Record<string, string> = { ACEITE: "Aceite", RECUSADA: `Recusada${swap.declineReason ? `: “${swap.declineReason}”` : ""}`, CANCELADA: "Cancelada", EXPIRADA: "Expirou" };
    events.push([swap.respondedAt, label[swap.status] ?? swap.status]);
  }

  return (
    <>
      {swap.message && (
        <div className="section">
          <div className="group"><div className="row"><Avatar id={swap.requester.userId} name={swap.requester.displayName} /><span className="grow" style={{ fontSize: 15 }}>“{swap.message}”</span></div></div>
        </div>
      )}
      {give && get && <SwapLine give={give as ShiftRef & { date: string }} get={get as ShiftRef & { date: string }} otherName={other.displayName} />}

      {active && iAmTarget && !mode && (
        <div className="section">
          <button className="btn primary" style={{ width: "100%" }} disabled={action.isPending} onClick={() => run("accept", undefined, "Troca aceite · documento emitido")}>Aceitar</button>
          <div className="btnrow" style={{ marginTop: 10 }}>
            {swap.status === "PENDENTE" ? <button className="btn" onClick={() => setMode("hold")}>Aguardar</button> : <span />}
            <button className="btn red" style={swap.status !== "PENDENTE" ? { gridColumn: "1 / -1" } : undefined} onClick={() => setMode("decline")}>Recusar</button>
          </div>
        </div>
      )}
      {active && iAmTarget && mode && (
        <div className="section">
          <div className="hd"><span>{mode === "hold" ? `Mensagem para ${other.displayName}` : "Motivo"}</span></div>
          <div className="group">
            {(mode === "hold" ? HOLD : DECLINE).map((q) => (
              <button key={q} className="row" disabled={action.isPending}
                onClick={() => run(mode, q, mode === "hold" ? `${other.displayName} foi avisado para aguardar` : "Pedido recusado")}>
                <span className="grow t" style={{ fontSize: 16 }}>{q}</span>
              </button>
            ))}
          </div>
          <div className="btnrow" style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => setMode(null)}>Voltar</button>
            <button className={`btn ${mode === "hold" ? "primary" : "red"}`} disabled={action.isPending}
              onClick={() => run(mode, undefined, mode === "hold" ? `${other.displayName} foi avisado para aguardar` : "Pedido recusado")}>
              {mode === "hold" ? "Aguardar" : "Recusar"}
            </button>
          </div>
        </div>
      )}
      {active && !iAmTarget && (
        <div className="section">
          <div className="group"><button className="row danger center" disabled={action.isPending} onClick={() => run("cancel", undefined, "Pedido cancelado")}><span className="t">Cancelar pedido</span></button></div>
        </div>
      )}
      {swap.status === "ACEITE" && swap.documentReference && (
        <div className="section">
          <a className="btn primary" style={{ display: "grid", placeItems: "center" }} href={`/api/v1/swaps/${swap.id}/document.pdf`} target="_blank" rel="noopener">
            Documento de troca
          </a>
        </div>
      )}

      <div className="section">
        <div className="hd"><span>Registo</span></div>
        <div className="group">
          {events.map(([t, x]) => (
            <div className="row" key={t + x}><span className="grow" style={{ fontSize: 15 }}>{x}</span><span className="v num" style={{ fontSize: 13 }}>{stamp(t)}</span></div>
          ))}
          {active && <div className="row"><span className="grow" style={{ fontSize: 15, color: "var(--label-2)" }}>Expira</span><span className="v num" style={{ fontSize: 13 }}>{stamp(swap.expiresAt)}</span></div>}
        </div>
      </div>
    </>
  );
}

// ── o meu dia ──

export function DaySheet({ date, onRequestSwap }: { date: string; onRequestSwap: (date: string) => void }) {
  const { types } = useApp();
  const toast = useToast();
  const shifts = useMyShifts(date, date);
  const paint = usePaint();
  const add = useAddShift();
  const del = useDeleteShift();
  const [mode, setMode] = useState<null | "change" | "extra">(null);
  const [extra, setExtra] = useState({ typeId: "", start: "18:00", hours: "4" });
  const list = shifts.data ?? [];
  const variable = types.filter((t) => t.kind === "WORK" && !t.allDay && !t.startTime);
  const future = date > today();

  return (
    <>
      {list.length === 0 && !shifts.isLoading && <div className="section"><div className="empty" style={{ background: "var(--card)", borderRadius: 12 }}>Sem serviço neste dia.</div></div>}
      {list.map((s) => (
        <div className="section" key={s.id}>
          <div className="shiftblock">
            <ShiftPill shift={s} size="lg" />
            <div className="grow" style={{ flex: 1 }}>
              <div className="t1">{s.name}</div>
              <div className="t2">{hoursLabel(s)}{s.source === "SWAP" ? " · por troca" : ""}</div>
              {s.notes && <div className="t2">{s.notes}</div>}
            </div>
            <button className="xbtn" aria-label={`Apagar ${s.code}`} disabled={del.isPending}
              onClick={() => del.mutate(s.id, { onSuccess: () => toast("Serviço apagado"), onError: (e) => toast(errorText(e), "error") })}>
              <Icon name="x" />
            </button>
          </div>
        </div>
      ))}

      {mode === "change" && (
        <div className="section">
          <div className="hd"><span>Serviço</span></div>
          <div className="typegrid">
            {types.filter((t) => t.allDay || t.startTime).map((t) => (
              <button key={t.id} aria-pressed={list.some((s) => s.shiftTypeId === t.id)} disabled={paint.isPending}
                onClick={() => paint.mutate({ shiftTypeId: t.id, dates: [date] }, {
                  onSuccess: (r) => { toast(r.warnings[0]?.message ?? "Serviço atualizado"); setMode(null); },
                  onError: (e) => toast(errorText(e), "error"),
                })}>
                <Pill code={t.code} color={t.color} kind={t.kind} size="md" />
                <span>{t.name.replace(/ \(.*\)$/, "")}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {mode === "extra" && (
        <form className="section" onSubmit={(e) => {
          e.preventDefault();
          const typeId = extra.typeId || variable[0]?.id;
          if (!typeId) return;
          add.mutate({ shiftTypeId: typeId, date, start: extra.start, durationMinutes: Math.round(Number(extra.hours.replace(",", ".")) * 60) }, {
            onSuccess: (r) => { toast(r.warnings[0]?.message ?? "Serviço acrescentado"); setMode(null); },
            onError: (e) => toast(errorText(e), "error"),
          });
        }}>
          <div className="group">
            <div className="row"><span className="grow t">Tipo</span>
              <select className="field" style={{ width: "auto" }} value={extra.typeId || variable[0]?.id} onChange={(e) => setExtra({ ...extra, typeId: e.target.value })}>
                {variable.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div className="row"><span className="grow t">Início</span><input className="field" style={{ width: "auto", textAlign: "right" }} type="time" required value={extra.start} onChange={(e) => setExtra({ ...extra, start: e.target.value })} /></div>
            <div className="row"><span className="grow t">Horas</span><input className="field" style={{ width: 70, textAlign: "right" }} inputMode="decimal" required value={extra.hours} onChange={(e) => setExtra({ ...extra, hours: e.target.value })} /></div>
          </div>
          <div className="btnrow" style={{ marginTop: 12 }}>
            <button type="button" className="btn" onClick={() => setMode(null)}>Voltar</button>
            <button className="btn primary" disabled={add.isPending}>Acrescentar</button>
          </div>
        </form>
      )}

      {!mode && (
        <div className="section">
          <div className="group">
            <button className="row tint" onClick={() => setMode("change")}><span className="grow t">{list.length ? "Mudar serviço" : "Marcar serviço"}</span></button>
            {variable.length > 0 && <button className="row tint" onClick={() => setMode("extra")}><span className="grow t">Acrescentar {variable.map((t) => t.code).join(" / ")}</span></button>}
            {future && list.some((s) => s.kind !== "ABSENCE") && (
              <button className="row tint" onClick={() => onRequestSwap(date)}><span className="grow t">Pedir troca a um camarada</span></button>
            )}
            {list.length > 0 && (
              <button className="row danger" disabled={paint.isPending}
                onClick={() => paint.mutate({ shiftTypeId: null, dates: [date] }, { onSuccess: () => toast("Dia limpo"), onError: (e) => toast(errorText(e), "error") })}>
                <span className="grow t">Limpar dia</span>
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export const dayTitle = (d: string) => cap(longDate(d));
