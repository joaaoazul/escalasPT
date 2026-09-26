"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { NavBar, LargeTitle } from "./NavBar";

/** Ecrã de quem ainda não está num grupo de folgas: introduz o código que o comandante de grupo lhe deu. */
export function JoinGroup({ admin }: { admin: boolean }) {
  const router = useRouter();
  const [code, setCode] = useState("");
  return (
    <main className="screen">
      <NavBar title="Turnos" right={admin ? <Link className="tbtn" href="/admin">Administração</Link> : undefined} />
      <LargeTitle>Entrar num grupo</LargeTitle>
      <form
        className="section"
        onSubmit={(e) => {
          e.preventDefault();
          const c = code.trim();
          if (!c) return;
          router.push(`/convite/${encodeURIComponent(c)}`);
        }}
      >
        <div className="hd"><span>Código do convite</span></div>
        <div className="group">
          <div className="row">
            <input id="invite-code" className="field code-box" autoCapitalize="characters" autoComplete="off" placeholder="XXXXX-XXXXX-XXXXX-XXXXX"
              value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
          </div>
        </div>
        <div className="ft">O comandante do teu grupo de folgas envia-te o código.</div>
        <div style={{ marginTop: 16 }}>
          <button className="btn primary" style={{ width: "100%" }} type="submit" disabled={!code.trim()}>Continuar</button>
        </div>
      </form>
      {admin && (
        <div className="section">
          <div className="group"><Link className="row tint" href="/admin"><span className="grow t">Administração do posto</span></Link></div>
        </div>
      )}
    </main>
  );
}

