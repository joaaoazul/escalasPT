"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api/client";
import type { Member } from "@/lib/api/models";
import { useApp } from "@/lib/app-context";
import { stamp } from "@/lib/dates";
import { useCreateInvite, useInvites, useRemoveMember, useRevokeInvite } from "@/lib/queries";
import { Avatar } from "./Avatar";
import { useSheet } from "./Sheet";
import { useToast } from "./Toast";
import { MemberSheet } from "./sheets";

const RANKS = ["Guarda", "Guarda Principal", "Cabo", "Cabo-Chefe", "Cabo-Mor"];
const STATUS: Record<string, string> = { PENDING: "por aceitar", ACCEPTED: "aceite", REVOKED: "revogado", EXPIRED: "expirou" };

/** Militares do grupo de folgas. O comandante de grupo convida, revoga convites e remove militares. */
export function MembersSheet() {
  const { me, membership, posto } = useApp();
  const sheet = useSheet();
  const toast = useToast();
  const group = posto.groups.find((g) => g.id === membership.groupId);
  const members: Member[] = group?.members ?? [];
  const commander = membership.commander;
  const invites = useInvites(membership.groupId, commander);
  const create = useCreateInvite(membership.groupId);
  const revoke = useRevokeInvite(membership.groupId);
  const remove = useRemoveMember(membership.groupId);
  const [form, setForm] = useState({ rank: "Guarda", name: "", email: "" });
  const [code, setCode] = useState<string | null>(null);
  const fail = (e: unknown) => toast(e instanceof ApiError ? e.message : "Erro", "error");

  return (
    <>
      <div className="section">
        <div className="hd"><span>{members.length} militares</span></div>
        <div className="group" style={{ "--inset": "58px" } as React.CSSProperties}>
          {members.map((m) => (
            <div className="row" key={m.userId}>
              <Avatar id={m.userId} name={m.displayName} />
              <button className="grow" style={{ textAlign: "left" }}
                onClick={() => sheet.open(m.displayName, () => <MemberSheet userId={m.userId} displayName={m.displayName} subtitle={`${membership.groupName}${m.commander ? " · comandante de grupo" : ""}`} />)}>
                <div className="t">{m.displayName}{m.userId === me.id ? " (eu)" : ""}</div>
                <div className="s">{m.commander ? "Comandante de grupo" : "Militar"}{m.serviceNumber ? ` · n.º ${m.serviceNumber}` : ""}</div>
              </button>
              {commander && !m.commander && (
                <button className="btn small red" style={{ height: 30 }} disabled={remove.isPending}
                  onClick={() => remove.mutate(m.userId, { onSuccess: () => toast(`${m.displayName} saiu do grupo`), onError: fail })}>
                  Remover
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {commander && (
        <>
          <form className="section" onSubmit={(e) => {
            e.preventDefault();
            create.mutate(
              { rank: form.rank, name: form.name.trim() || undefined, email: form.email.trim() || undefined },
              { onSuccess: (r) => { setCode(r.code); setForm({ rank: "Guarda", name: "", email: "" }); }, onError: fail },
            );
          }}>
            <div className="hd"><span>Convidar militar</span></div>
            <div className="group">
              <div className="row"><span className="grow t">Posto</span>
                <select className="field" style={{ width: "auto" }} value={form.rank} onChange={(e) => setForm({ ...form, rank: e.target.value })}>{RANKS.map((r) => <option key={r}>{r}</option>)}</select>
              </div>
              <div className="row"><input id="invite-name" className="field" placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="row"><input id="invite-email" className="field" type="email" placeholder="Email (opcional)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
              <button className="row tint" type="submit" disabled={create.isPending}><span className="grow t">Criar convite</span></button>
            </div>
          </form>
          {code && (
            <div className="section">
              <div className="group">
                <div className="row" style={{ alignItems: "center" }}>
                  <span className="grow"><div className="code-box" data-testid="invite-code">{code}</div><div className="s">Uso único · válido 7 dias</div></span>
                  <button className="btn small" onClick={async () => {
                    const url = `${location.origin}/convite/${code}`;
                    try {
                      if (navigator.share) await navigator.share({ title: "Convite Turnos", text: `Convite para o ${membership.groupName}`, url });
                      else { await navigator.clipboard.writeText(url); toast("Ligação copiada"); }
                    } catch { /* partilha cancelada */ }
                  }}>Partilhar</button>
                </div>
              </div>
            </div>
          )}
          {!!invites.data?.length && (
            <div className="section">
              <div className="hd"><span>Convites</span></div>
              <div className="group">
                {invites.data.map((i) => (
                  <div className="row" key={i.id}>
                    <span className="grow">
                      <div className="t">{[i.rank, i.name].filter(Boolean).join(" ") || "Convite"}</div>
                      <div className="s">{i.email ?? "sem email"} · {STATUS[i.status] ?? i.status}{i.acceptedAt ? ` ${stamp(i.acceptedAt)}` : ""}</div>
                    </span>
                    {i.status === "PENDING" && (
                      <button className="tbtn" style={{ color: "var(--red)", fontSize: 15 }} disabled={revoke.isPending}
                        onClick={() => revoke.mutate(i.id, { onSuccess: () => toast("Convite revogado"), onError: fail })}>Revogar</button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
