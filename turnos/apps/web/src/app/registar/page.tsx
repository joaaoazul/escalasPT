"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";

const RANKS = ["Guarda", "Guarda Principal", "Cabo", "Cabo-Chefe", "Cabo-Mor", "Furriel", "2.º Sargento", "1.º Sargento", "Sargento-Ajudante", "Sargento-Chefe", "Sargento-Mor"];

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [f, setF] = useState({ fullName: "", rank: "Guarda", serviceNumber: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = params.get("next")?.startsWith("/") ? params.get("next")! : "/";
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <main className="auth">
      <div className="brand"><b>Criar conta</b><p>Depois entras no teu grupo com o código do convite</p></div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await unwrap(api.POST("/api/v1/auth/register", {
              body: { ...f, serviceNumber: f.serviceNumber || (undefined as never) },
            }) as never);
            qc.clear();
            router.replace(next);
          } catch (err) {
            setError(err instanceof ApiError ? (err.code === "validation" ? "Verifica os dados (palavra-passe com pelo menos 10 caracteres)" : err.message) : "Sem ligação ao servidor");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="section" style={{ marginTop: 8 }}>
          <div className="group">
            <div className="row"><span className="grow t">Posto</span>
              <select id="rank" className="field" style={{ width: "auto" }} value={f.rank} onChange={set("rank")}>{RANKS.map((r) => <option key={r}>{r}</option>)}</select>
            </div>
            <div className="row"><input id="fullName" className="field" placeholder="Nome (ex.: Ana Silva)" required value={f.fullName} onChange={set("fullName")} /></div>
            <div className="row"><input id="serviceNumber" className="field" inputMode="numeric" pattern="[0-9]{1,5}" placeholder="N.º de ordem (opcional)" value={f.serviceNumber} onChange={set("serviceNumber")} /></div>
          </div>
        </div>
        <div className="section" style={{ marginTop: 18 }}>
          <div className="group">
            <div className="row"><input id="email" className="field" type="email" autoComplete="username" placeholder="Email" required value={f.email} onChange={set("email")} /></div>
            <div className="row"><input id="password" className="field" type="password" autoComplete="new-password" minLength={10} placeholder="Palavra-passe (mín. 10 caracteres)" required value={f.password} onChange={set("password")} /></div>
          </div>
          {error && <div className="error-text" role="alert">{error}</div>}
        </div>
        <div className="section" style={{ marginTop: 18 }}>
          <button className="btn primary" style={{ width: "100%" }} disabled={busy}>Criar conta</button>
        </div>
      </form>
      <div className="section" style={{ textAlign: "center", fontSize: 15 }}>
        <Link href={`/entrar${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`}>Já tenho conta</Link>
      </div>
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
