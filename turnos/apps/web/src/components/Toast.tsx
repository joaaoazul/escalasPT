"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { Icon } from "./Icon";

const ToastCtx = createContext<(msg: string, kind?: "ok" | "error") => void>(() => {});

export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<{ msg: string; kind: "ok" | "error"; show: boolean }>({ msg: "", kind: "ok", show: false });
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const toast = useCallback((msg: string, kind: "ok" | "error" = "ok") => {
    setState({ msg, kind, show: true });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState((s) => ({ ...s, show: false })), kind === "error" ? 4000 : 2600);
  }, []);
  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className={`toast ${state.show ? "show" : ""}`} role="status" aria-live="polite">
        <Icon name={state.kind === "error" ? "warn" : "check"} style={{ color: state.kind === "error" ? "var(--red)" : "var(--green)" }} />
        <span>{state.msg}</span>
      </div>
    </ToastCtx.Provider>
  );
}
