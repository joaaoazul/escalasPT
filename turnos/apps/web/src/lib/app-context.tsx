"use client";

import { createContext, useContext } from "react";
import type { Me, Membership, Posto, ShiftType } from "./api/models";

export type AppData = {
  me: Me;
  membership: Membership;
  posto: Posto;
  types: ShiftType[];
  typeById: Map<string, ShiftType>;
};

export const AppCtx = createContext<AppData | null>(null);

export function useApp(): AppData {
  const v = useContext(AppCtx);
  if (!v) throw new Error("Fora da área autenticada");
  return v;
}
