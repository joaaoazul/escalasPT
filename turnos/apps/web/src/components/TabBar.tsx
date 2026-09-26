"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";

const TABS = [
  { href: "/", label: "Hoje", icon: "today" },
  { href: "/calendario", label: "Calendário", icon: "cal" },
  { href: "/grupo", label: "Grupo", icon: "group" },
  { href: "/posto", label: "Posto", icon: "posto" },
  { href: "/horas", label: "Horas", icon: "chart" },
] as const;

export function TabBar({ badge }: { badge?: number }) {
  const path = usePathname();
  return (
    <nav className="tabbar" aria-label="Secções" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
      {TABS.map((t) => {
        const active = t.href === "/" ? path === "/" : path.startsWith(t.href);
        return (
          <Link key={t.href} href={t.href} className="tab" aria-current={active ? "page" : undefined} aria-selected={active}>
            <Icon name={t.icon} size={26} />
            {t.label}
            {t.href === "/grupo" && !!badge && <span className="badge">{badge}</span>}
          </Link>
        );
      })}
    </nav>
  );
}
