"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "@/lib/api/client";

/** Repor a palavra-passe com o código que o comandante de grupo gerou. */
export default function Page() {
  const router = useRouter();
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <main className="auth">
      <div className="brand"><b>Nova palavra-passe</b><p>Pede o código ao comandante do teu grupo de folgas</p></div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await unwrap(api.POST("/api/v1/auth/password-reset", { body: { code: code.trim(), password } }) as never);
            qc.clear();
            router.replace("/");
          } catch (err) {
            setError(err instanceof ApiError
              ? err.code === "validation" ? "A palavra-passe precisa de pelo menos 10 caracteres" : err.message
              : "Sem ligação ao servidor");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="section" style={{ marginTop: 8 }}>
          <div className="group">
            <div className="row">
              <input id="reset-code" className="field code-box" style={{ fontSize: 17 }} autoCapitalize="characters" autoComplete="one-time-code"
                placeholder="XXXX-XXXX-XXXX" required value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
            </div>
            <div className="row">
              <input id="new-password" className="field" type="password" autoComplete="new-password" minLength={10}
                placeholder="Nova palavra-passe (mín. 10 caracteres)" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
          </div>
          {error && <div className="error-text" role="alert">{error}</div>}
        </div>
        <div className="section" style={{ marginTop: 18 }}>
          <button className="btn primary" style={{ width: "100%" }} disabled={busy}>Guardar e entrar</button>
        </div>
      </form>
      <div className="section" style={{ textAlign: "center", fontSize: 15 }}>
        <Link href="/entrar">Voltar</Link>
      </div>
    </main>
  );
}
