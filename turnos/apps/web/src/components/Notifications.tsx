"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { stamp } from "@/lib/dates";
import { disablePush, enablePush, pushState, type PushState } from "@/lib/push";
import { useMarkAllRead, useNotifications } from "@/lib/queries";
import { Icon } from "./Icon";
import { useSheet } from "./Sheet";
import { useToast } from "./Toast";

export function Bell() {
  const sheet = useSheet();
  const n = useNotifications();
  const unread = n.data?.unread ?? 0;
  return (
    <button className="tbtn" style={{ position: "relative" }} aria-label={unread ? `Notificações, ${unread} por ler` : "Notificações"}
      onClick={() => sheet.open("Notificações", () => <NotificationsSheet />)}>
      <Icon name="bell" />
      {!!unread && <span className="badge" style={{ top: 2, left: 14 }}>{unread}</span>}
    </button>
  );
}

function NotificationsSheet() {
  const router = useRouter();
  const sheet = useSheet();
  const n = useNotifications();
  const read = useMarkAllRead();
  const unread = n.data?.unread ?? 0;
  const { mutate } = read;
  useEffect(() => {
    if (unread > 0) mutate();
  }, [unread, mutate]);
  const items = n.data?.items ?? [];
  return (
    <>
      <PushToggle />
      <div className="section">
        {items.length === 0 ? (
          <div className="empty" style={{ background: "var(--card)", borderRadius: 12 }}>Sem notificações.</div>
        ) : (
          <div className="group">
            {items.map((x) => (
              <button key={x.id} className="row" style={{ alignItems: "flex-start" }} onClick={() => { sheet.close(); if (x.url) router.push(x.url); }}>
                <span style={{ width: 8, height: 8, borderRadius: 4, marginTop: 8, background: x.readAt ? "transparent" : "var(--tint)", flex: "none" }} />
                <span className="grow">
                  <div className="t" style={{ fontWeight: x.readAt ? 400 : 600 }}>{x.title}</div>
                  <div className="s">{x.body}</div>
                </span>
                <span className="v num" style={{ fontSize: 13 }}>{stamp(x.createdAt)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

const LABEL: Record<PushState, string> = {
  unsupported: "Este browser não suporta notificações",
  "ios-install": "Adiciona o Turnos ao ecrã principal (Partilhar › Adicionar ao ecrã principal) para receberes notificações",
  "server-off": "",
  denied: "Notificações bloqueadas nas definições do telemóvel",
  off: "",
  on: "",
};

export function PushToggle() {
  const toast = useToast();
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    pushState().then(setState).catch(() => setState("unsupported"));
  }, []);
  if (!state || state === "server-off") return null;
  const toggle = async () => {
    setBusy(true);
    try {
      setState(state === "on" ? await disablePush() : await enablePush());
    } catch {
      toast("Não foi possível ativar as notificações", "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="section">
      <div className="group">
        <div className="row">
          <span className="grow t">Notificações no telemóvel</span>
          {(state === "on" || state === "off") && (
            <button role="switch" aria-checked={state === "on"} className={`switch ${state === "on" ? "on" : ""}`} disabled={busy} onClick={toggle}>
              <span />
            </button>
          )}
        </div>
      </div>
      {LABEL[state] && <div className="ft">{LABEL[state]}</div>}
    </div>
  );
}
