"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { RegisterForm } from "@/components/RegisterForm";

/** Registo com o código do convite escrito à mão (quem abre o link do convite vai para /convite/…). */
export default function Page() {
  const router = useRouter();
  return (
    <main className="auth">
      <div className="brand"><b>Criar conta</b><p>Com o convite do comandante do teu grupo de folgas</p></div>
      <RegisterForm onDone={() => router.replace("/grupo")} />
      <div className="section" style={{ textAlign: "center", fontSize: 15 }}>
        <Link href="/entrar">Já tenho conta</Link>
      </div>
    </main>
  );
}
