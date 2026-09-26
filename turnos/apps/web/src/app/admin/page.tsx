"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { Posto } from "@/lib/api/models";
import { useMe } from "@/lib/queries";
import { NavBar, LargeTitle } from "@/components/NavBar";
import { useToast } from "@/components/Toast";

/** Administração: cria postos e grupos de folgas e nomeia o comandante de cada grupo (por convite). */
export default function Page() {
  const me = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const postos = useQuery({ queryKey: ["admin-postos"], enabled: !!me.data?.admin, queryFn: () => unwrap<Posto[]>(api.GET("/api/v1/postos") as never) });
  const [novo, setNovo] = useState({ name: "", location: "" });
  const [codes, setCodes] = useState<Record<string, string>>({});
  const onError = (e: unknown) => toast(e instanceof ApiError ? e.message : "Erro", "error");

  const createPosto = useMutation({
    mutationFn: () => unwrap<Posto>(api.POST("/api/v1/postos", { body: { ...novo, timeZone: "Europe/Lisbon" } }) as never),
    onSuccess: () => { setNovo({ name: "", location: "" }); qc.invalidateQueries({ queryKey: ["admin-postos"] }); toast("Posto criado"); },
    onError,
  });
  const createGroup = useMutation({
    mutationFn: (v: { postoId: string; name: string }) =>
      unwrap(api.POST("/api/v1/postos/{postoId}/groups", { params: { path: { postoId: v.postoId } }, body: { name: v.name } }) as never),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-postos"] }),
    onError,
  });
  const inviteCommander = useMutation({
    mutationFn: (groupId: string) =>
      unwrap<{ code: string }>(api.POST("/api/v1/groups/{groupId}/invites", { params: { path: { groupId } }, body: { role: "COMMANDER" } }) as never),
    onError,
  });

  if (me.isLoading) return <div className="center-msg"><div className="spinner" /></div>;
  if (!me.data?.admin) return <div className="center-msg"><p>Só o administrador tem acesso.</p><Link href="/">Voltar</Link></div>;

  return (
    <main className="screen" style={{ paddingBottom: 40 }}>
      <NavBar title="Administração" left={<Link className="tbtn" href="/">Voltar</Link>} />
      <LargeTitle>Administração</LargeTitle>

      <form className="section" onSubmit={(e) => { e.preventDefault(); createPosto.mutate(); }}>
        <div className="hd"><span>Novo posto</span></div>
        <div className="group">
          <div className="row"><input id="posto-name" className="field" placeholder="Posto Territorial de …" required value={novo.name} onChange={(e) => setNovo({ ...novo, name: e.target.value })} /></div>
          <div className="row"><input id="posto-location" className="field" placeholder="Localidade (Quartel em …)" required value={novo.location} onChange={(e) => setNovo({ ...novo, location: e.target.value })} /></div>
          <button className="row tint" type="submit" disabled={createPosto.isPending}><span className="grow t">Criar posto</span></button>
        </div>
      </form>

      {(postos.data ?? []).map((p) => (
        <div className="section" key={p.id}>
          <div className="hd"><span>{p.name}</span></div>
          <div className="group">
            {p.groups.map((g) => {
              const cmd = g.members.find((m) => m.commander);
              return (
                <div className="row" key={g.id} style={{ alignItems: "flex-start" }}>
                  <span className="grow">
                    <div className="t">{g.name}</div>
                    <div className="s">{cmd ? `Comandante: ${cmd.displayName}` : "Sem comandante"} · {g.members.length} militares</div>
                    {codes[g.id] && <div className="code-box" style={{ fontSize: 16, marginTop: 6 }}>{codes[g.id]}</div>}
                  </span>
                  <button className="btn small" disabled={inviteCommander.isPending}
                    onClick={() => inviteCommander.mutate(g.id, { onSuccess: (r) => setCodes({ ...codes, [g.id]: r.code }) })}>
                    {cmd ? "Novo comandante" : "Convidar comandante"}
                  </button>
                </div>
              );
            })}
            <NewGroup onCreate={(name) => createGroup.mutate({ postoId: p.id, name })} />
          </div>
        </div>
      ))}
    </main>
  );
}

function NewGroup({ onCreate }: { onCreate: (name: string) => void }) {
  const [name, setName] = useState("");
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); if (name.trim()) { onCreate(name.trim()); setName(""); } }}>
      <input className="field" placeholder="Novo grupo de folgas (ex.: Grupo 1)" value={name} onChange={(e) => setName(e.target.value)} />
      <button className="tbtn" type="submit" disabled={!name.trim()}>Criar</button>
    </form>
  );
}
