"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";

function safeNext(v: string | null): string {
  return v && v.startsWith("/") && !v.startsWith("//") ? v : "/";
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get("next"));

  return (
    <main className="auth">
      <div className="brand"><b>Turnos</b><p>Escala, grupo de folgas e trocas</p></div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await unwrap(api.POST("/api/v1/auth/login", { body: { email, password } }) as never);
            qc.clear();
            router.replace(next);
          } catch (err) {
            setError(err instanceof ApiError ? err.message : "Sem ligação ao servidor");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="section" style={{ marginTop: 8 }}>
          <div className="group">
            <div className="row"><input id="email" className="field" type="email" autoComplete="username" placeholder="Email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div className="row"><input id="password" className="field" type="password" autoComplete="current-password" placeholder="Palavra-passe" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          </div>
          {error && <div className="error-text" role="alert">{error}</div>}
        </div>
        <div className="section" style={{ marginTop: 18 }}>
          <button className="btn primary" style={{ width: "100%" }} disabled={busy}>Entrar</button>
        </div>
      </form>
      <div className="section" style={{ textAlign: "center", fontSize: 15 }}>
        <Link href={`/registar${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`}>Criar conta</Link>
      </div>
    </main>
  );
}

export default function Page() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
