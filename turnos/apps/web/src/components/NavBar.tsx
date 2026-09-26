"use client";

import { useEffect, useState } from "react";

/** Barra de navegação iOS: o título grande colapsa para a barra quando se faz scroll. */
export function NavBar({ title, left, right }: { title: string; left?: React.ReactNode; right?: React.ReactNode }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 36);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <>
      <header className={`nav ${scrolled ? "scrolled" : ""}`}>
        <div className="nav-row">
          <div className="nav-l">{left}</div>
          <div className="nav-title">{title}</div>
          <div className="nav-r">{right}</div>
        </div>
      </header>
      <div className="spacer-top" />
    </>
  );
}

export function LargeTitle({ children, eyebrow, aside }: { children: React.ReactNode; eyebrow?: string; aside?: React.ReactNode }) {
  return (
    <>
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <div className="large" style={aside ? { justifyContent: "space-between", alignItems: "center" } : undefined}>
        <h1>{children}</h1>
        {aside}
      </div>
    </>
  );
}
