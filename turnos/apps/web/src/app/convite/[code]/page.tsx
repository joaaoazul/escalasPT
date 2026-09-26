"use client";

import Link from "next/link";
import { use } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { useAcceptInvite, useInvitePreview, useMe } from "@/lib/queries";
import { useToast } from "@/components/Toast";

const STATUS: Record<string, string> = { ACCEPTED: "Este convite já foi usado.", REVOKED: "Este convite foi revogado.", EXPIRED: "Este convite expirou." };

export default function Page({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const router = useRouter();
  const toast = useToast();
  const me = useMe();
  const preview = useInvitePreview(code);
  const accept = useAcceptInvite();
  const here = `/convite/${encodeURIComponent(code)}`;

  if (me.isLoading || preview.isLoading) return <div className="center-msg"><div className="spinner" /></div>;
  if (me.error) {
    return (
      <main className="auth">
        <div className="brand"><b>Convite</b><p>Entra ou cria conta para aceitar o convite</p></div>
        <div className="section"><div className="btnrow">
          <Link className="btn" style={{ display: "grid", placeItems: "center" }} href={`/registar?next=${encodeURIComponent(here)}`}>Criar conta</Link>
          <Link className="btn primary" style={{ display: "grid", placeItems: "center" }} href={`/entrar?next=${encodeURIComponent(here)}`}>Entrar</Link>
        </div></div>
      </main>
    );
  }
  if (preview.error || !preview.data) {
    return <div className="center-msg"><p>Código de convite inválido.</p><Link href="/">Voltar</Link></div>;
  }
  const p = preview.data;
  return (
    <main className="auth">
      <div className="brand"><b>{p.groupName}</b><p>{p.postoName}</p></div>
      <div className="section">
        <div className="group">
          {p.invitedBy && <div className="row"><span className="grow t">Convidado por</span><span className="v">{p.invitedBy}</span></div>}
          <div className="row"><span className="grow t">Partilhas</span><span className="v">Calendário de serviço</span></div>
        </div>
      </div>
      {p.status !== "PENDING" ? (
        <div className="section"><div className="error-text" style={{ padding: 0 }}>{STATUS[p.status] ?? "Convite inválido."}</div></div>
      ) : (
        <div className="section">
          <button
            className="btn primary"
            style={{ width: "100%" }}
            disabled={accept.isPending}
            onClick={() =>
              accept.mutate(code, {
                onSuccess: () => {
                  toast(`Entraste no ${p.groupName}`);
                  router.replace("/grupo");
                },
                onError: (e) => toast(e instanceof ApiError ? e.message : "Não foi possível aceitar", "error"),
              })
            }
          >
            Entrar no grupo
          </button>
        </div>
      )}
    </main>
  );
}
