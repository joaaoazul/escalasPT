"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect, useMemo } from "react";
import { ApiError } from "@/lib/api/client";
import { AppCtx } from "@/lib/app-context";
import { useMe, useMembership, usePosto, useShiftTypes, useSwaps } from "@/lib/queries";
import { TabBar } from "@/components/TabBar";
import { SheetProvider } from "@/components/Sheet";
import { JoinGroup } from "@/components/JoinGroup";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const me = useMe();
  const unauthorized = me.error instanceof ApiError && me.error.status === 401;
  const membership = useMembership(!!me.data);
  const posto = usePosto(membership.data?.postoId);
  const types = useShiftTypes(membership.data?.postoId);
  const received = useSwaps("received");

  useEffect(() => {
    if (unauthorized) router.replace(`/entrar?next=${encodeURIComponent(path)}`);
  }, [unauthorized, router, path]);

  const data = useMemo(() => {
    if (!me.data || !membership.data || !posto.data || !types.data) return null;
    return {
      me: me.data,
      membership: membership.data,
      posto: posto.data,
      types: types.data,
      typeById: new Map(types.data.map((t) => [t.id, t])),
    };
  }, [me.data, membership.data, posto.data, types.data]);

  if (me.isLoading || unauthorized || membership.isLoading || (membership.data && (posto.isLoading || types.isLoading))) {
    return (
      <div className="center-msg">
        <div className="spinner" aria-label="A carregar" />
      </div>
    );
  }
  if (me.error || membership.error || posto.error || types.error) {
    return <div className="center-msg">Não foi possível ligar ao servidor. Tenta de novo daqui a pouco.</div>;
  }
  if (membership.data === null && me.data) {
    return <JoinGroup admin={me.data.admin} />;
  }
  if (!data) return null;

  const pending = (received.data ?? []).filter((s) => s.status === "PENDENTE").length;
  return (
    <AppCtx.Provider value={data}>
      <SheetProvider>
        <main className="screen">{children}</main>
        <TabBar badge={pending} />
      </SheetProvider>
    </AppCtx.Provider>
  );
}
