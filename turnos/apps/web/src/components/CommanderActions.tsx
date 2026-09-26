"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api/client";
import { useApp } from "@/lib/app-context";
import { usePasswordReset, useRemoveMember, useTransferCommand } from "@/lib/queries";
import { shareLink } from "@/lib/share";
import { useSheet } from "./Sheet";
import { useToast } from "./Toast";

/** O que o comandante de grupo pode fazer a um militar do seu grupo. As ações irreversíveis pedem confirmação. */
export function CommanderActions({ userId, displayName }: { userId: string; displayName: string }) {
  const { membership } = useApp();
  const sheet = useSheet();
  const toast = useToast();
  const reset = usePasswordReset();
  const transfer = useTransferCommand(membership.groupId);
  const remove = useRemoveMember(membership.groupId);
  const [code, setCode] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"transfer" | "remove" | null>(null);
  const fail = (e: unknown) => toast(e instanceof ApiError ? e.message : "Erro", "error");

  return (
    <>
      <div className="section">
        <div className="group">
          <button className="row tint" disabled={reset.isPending}
            onClick={() => reset.mutate({ groupId: membership.groupId, userId }, { onSuccess: (r) => setCode(r.code), onError: fail })}>
            <span className="grow t">Código para nova palavra-passe</span>
          </button>
          {code && (
            <div className="row" style={{ alignItems: "center" }}>
              <span className="grow"><div className="code-box" data-testid="reset-code">{code}</div><div className="s">Uso único · válido 24 horas</div></span>
              <button className="btn small" onClick={() => shareLink(`${location.origin}/repor`, "Turnos",
                `Código para a nova palavra-passe no Turnos: ${code}`, () => toast("Ligação copiada"))}>Enviar</button>
            </div>
          )}
        </div>
      </div>
      <div className="section">
        <div className="group">
          <button className="row tint" disabled={transfer.isPending} onClick={() => {
            if (confirm !== "transfer") return setConfirm("transfer");
            transfer.mutate(userId, { onSuccess: () => { toast(`${displayName} é o novo comandante de grupo`); sheet.close(); }, onError: fail });
          }}>
            <span className="grow t">{confirm === "transfer" ? `Confirmar: passar o comando a ${displayName}` : "Passar o comando do grupo"}</span>
          </button>
          <button className="row danger" disabled={remove.isPending} onClick={() => {
            if (confirm !== "remove") return setConfirm("remove");
            remove.mutate(userId, { onSuccess: () => { toast(`${displayName} saiu do grupo`); sheet.close(); }, onError: fail });
          }}>
            <span className="grow t">{confirm === "remove" ? "Confirmar remoção" : "Remover do grupo"}</span>
          </button>
        </div>
      </div>
    </>
  );
}
