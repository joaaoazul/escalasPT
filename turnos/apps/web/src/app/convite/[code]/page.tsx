"use client";

import Link from "next/link";
import { use } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { useAcceptInvite, useInvitePreview, useMe, useMembership } from "@/lib/queries";
import { RegisterForm } from "@/components/RegisterForm";
import { useToast } from "@/components/Toast";

const STATUS: Record<string, string> = { ACCEPTED: "Este convite já foi usado.", REVOKED: "Este convite foi revogado.", EXPIRED: "Este convite expirou." };

/** Link do convite: mostra o grupo e, conforme o caso, cria a conta e entra, entra no grupo, ou muda de grupo. */
export default function Page({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const router = useRouter();
  const toast = useToast();
  const me = useMe();
  const membership = useMembership(!!me.data);
  const preview = useInvitePreview(code);
  const accept = useAcceptInvite();
  const here = `/convite/${encodeURIComponent(code)}`;

  if (preview.isLoading || me.isLoading || (me.data && membership.isLoading)) return <div className="center-msg"><div className="spinner" /></div>;
  if (preview.error || !preview.data) {
    return <div className="center-msg"><p>Código de convite inválido.</p><Link href="/">Voltar</Link></div>;
  }
  const p = preview.data;
  const current = membership.data;
  const same = current?.groupId === p.groupId;

  return (
    <main className="auth">
      <div className="brand"><b>{p.groupName}</b><p>{p.postoName}</p></div>
      <div className="section">
        <div className="group">
          {p.invitedBy && <div className="row"><span className="grow t">Convidado por</span><span className="v">{p.invitedBy}</span></div>}
          {p.commander && <div className="row"><span className="grow t">Papel</span><span className="v">Comandante de grupo</span></div>}
          {current && !same && <div className="row"><span className="grow t">Sais do</span><span className="v">{current.groupName}</span></div>}
        </div>
      </div>

      {p.status !== "PENDING" ? (
        <div className="section"><div className="error-text" style={{ padding: 0 }}>{STATUS[p.status] ?? "Convite inválido."}</div></div>
      ) : !me.data ? (
        <>
          <RegisterForm code={code} prefill={{ email: p.email, name: p.name, rank: p.rank }} onDone={() => router.replace("/grupo")} />
          <div className="section" style={{ textAlign: "center", fontSize: 15 }}>
            <Link href={`/entrar?next=${encodeURIComponent(here)}`}>Já tenho conta</Link>
          </div>
        </>
      ) : same ? (
        <div className="section"><Link className="btn primary" style={{ display: "grid", placeItems: "center" }} href="/grupo">Já estás neste grupo</Link></div>
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
            {current ? `Mudar para o ${p.groupName}` : "Entrar no grupo"}
          </button>
        </div>
      )}
    </main>
  );
}
