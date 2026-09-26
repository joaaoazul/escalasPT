"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";
import { RANKS } from "@/lib/ranks";

type Prefill = { email?: string | null; name?: string | null; rank?: string | null };

/**
 * Criar conta. Com {@code code} (vindo do link do convite) o militar entra logo no grupo; sem ele, pede o código.
 * Os dados que o comandante já preencheu no convite vêm em {@code prefill}.
 */
export function RegisterForm({ code, prefill, onDone }: { code?: string; prefill?: Prefill; onDone: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState({
    inviteCode: code ?? "",
    rank: prefill?.rank ?? "Guarda",
    fullName: prefill?.name ?? "",
    serviceNumber: "",
    email: prefill?.email ?? "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: k === "inviteCode" ? e.target.value.toUpperCase() : e.target.value });

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await unwrap(api.POST("/api/v1/auth/register", {
            body: {
              ...f,
              inviteCode: f.inviteCode.trim() || (undefined as never),
              serviceNumber: f.serviceNumber || (undefined as never),
            },
          }) as never);
          qc.clear();
          onDone();
        } catch (err) {
          setError(err instanceof ApiError
            ? err.code === "validation" ? "Verifica os dados (palavra-passe com pelo menos 10 caracteres)" : err.message
            : "Sem ligação ao servidor");
        } finally {
          setBusy(false);
        }
      }}
    >
      {!code && (
        <div className="section" style={{ marginTop: 8 }}>
          <div className="hd"><span>Código do convite</span></div>
          <div className="group">
            <div className="row">
              <input id="inviteCode" className="field code-box" style={{ fontSize: 17 }} autoCapitalize="characters" autoComplete="off"
                placeholder="XXXXX-XXXXX-XXXXX-XXXXX" value={f.inviteCode} onChange={set("inviteCode")} />
            </div>
          </div>
        </div>
      )}
      <div className="section" style={{ marginTop: code ? 8 : 18 }}>
        <div className="group">
          <div className="row"><span className="grow t">Posto</span>
            <select id="rank" className="field" style={{ width: "auto" }} value={f.rank} onChange={set("rank")}>{RANKS.map((r) => <option key={r}>{r}</option>)}</select>
          </div>
          <div className="row"><input id="fullName" className="field" autoComplete="name" placeholder="Nome (ex.: Ana Silva)" required value={f.fullName} onChange={set("fullName")} /></div>
          <div className="row"><input id="serviceNumber" className="field" inputMode="numeric" pattern="[0-9]{1,5}" placeholder="N.º de ordem (opcional)" value={f.serviceNumber} onChange={set("serviceNumber")} /></div>
        </div>
      </div>
      <div className="section" style={{ marginTop: 18 }}>
        <div className="group">
          <div className="row"><input id="email" className="field" type="email" autoComplete="username" placeholder="Email" required
            readOnly={!!prefill?.email} value={f.email} onChange={set("email")} /></div>
          <div className="row"><input id="password" className="field" type="password" autoComplete="new-password" minLength={10}
            placeholder="Palavra-passe (mín. 10 caracteres)" required value={f.password} onChange={set("password")} /></div>
        </div>
        {error && <div className="error-text" role="alert">{error}</div>}
      </div>
      <div className="section" style={{ marginTop: 18 }}>
        <button className="btn primary" style={{ width: "100%" }} disabled={busy}>{code ? "Criar conta e entrar" : "Criar conta"}</button>
      </div>
    </form>
  );
}
