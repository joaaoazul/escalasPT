"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

type SheetContent = { title: string; render: () => React.ReactNode };
type Ctx = { open: (title: string, render: () => React.ReactNode) => void; close: () => void };

const SheetCtx = createContext<Ctx | null>(null);

export function useSheet(): Ctx {
  const c = useContext(SheetCtx);
  if (!c) throw new Error("SheetProvider em falta");
  return c;
}

/** Bottom sheet iOS: arrasta-se para baixo para fechar, fecha com Esc ou tocando fora. */
export function SheetProvider({ children }: { children: React.ReactNode }) {
  const [content, setContent] = useState<SheetContent | null>(null);
  const [visible, setVisible] = useState(false);
  const [dy, setDy] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<number | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const open = useCallback((title: string, render: () => React.ReactNode) => {
    setContent({ title, render });
    requestAnimationFrame(() => setVisible(true));
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
  }, []);
  const close = useCallback(() => {
    setVisible(false);
    setTimeout(() => setContent((c) => (c ? null : c)), 320);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  return (
    <SheetCtx.Provider value={{ open, close }}>
      {children}
      <div className={`backdrop ${visible ? "open" : ""}`} onClick={close} />
      <section
        className={`sheet ${visible ? "open" : ""} ${dragging ? "dragging" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={content?.title}
        aria-hidden={!visible}
        style={dy ? { transform: `translateY(${dy}px)` } : undefined}
      >
        <div
          className="sheet-hd"
          onPointerDown={(e) => {
            if ((e.target as HTMLElement).closest("button")) return;
            start.current = e.clientY;
            setDragging(true);
            (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => start.current !== null && setDy(Math.max(0, e.clientY - start.current))}
          onPointerUp={() => {
            if (dy > 90) close();
            start.current = null;
            setDragging(false);
            setDy(0);
          }}
          onPointerCancel={() => {
            start.current = null;
            setDragging(false);
            setDy(0);
          }}
        >
          <div className="grabber" />
          <div className="sheet-top">
            <h3>{content?.title}</h3>
            <button className="xbtn" onClick={close} aria-label="Fechar">
              <Icon name="x" />
            </button>
          </div>
        </div>
        <div className="sheet-body" ref={bodyRef}>
          {content?.render()}
        </div>
      </section>
    </SheetCtx.Provider>
  );
}
