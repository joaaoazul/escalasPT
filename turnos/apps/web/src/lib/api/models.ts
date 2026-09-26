import type { components } from "./schema";

type S = components["schemas"];
/** O OpenAPI gerado pelo springdoc não distingue campos anuláveis: declaram-se aqui. */
type Nullable<T, K extends keyof T> = Omit<T, K> & { [P in K]: T[P] | null };

export type Me = Nullable<S["MeResponse"], "rank" | "serviceNumber">;
export type Membership = S["MembershipView"];
export type Posto = Omit<S["PostoView"], "groups"> & { groups: Group[] };
export type Group = Omit<S["GroupView"], "members"> & { members: Member[] };
export type Member = Nullable<S["MemberView"], "rank" | "serviceNumber">;
export type ShiftType = Nullable<S["ShiftTypeInfo"], "startTime" | "durationMinutes">;
export type Shift = Nullable<S["ShiftDto"], "start" | "durationMinutes" | "notes">;
export type ShiftRef = Nullable<S["ShiftRef"], "start" | "durationMinutes">;
export type Swap = Omit<Nullable<S["SwapDto"], "message" | "holdMessage" | "declineReason" | "heldAt" | "respondedAt" | "documentReference">,
  "requesterShift" | "targetShift"> & { requesterShift: ShiftRef | null; targetShift: ShiftRef | null };
export type Invite = Nullable<S["InviteView"], "email" | "name" | "rank" | "acceptedAt">;
export type InvitePreview = Nullable<S["InvitePreview"], "invitedBy" | "email" | "name" | "rank">;
export type Warning = { code: string; severity: string; date: string; message: string };

export type SwapStatus = "PENDENTE" | "EM_ESPERA" | "ACEITE" | "RECUSADA" | "CANCELADA" | "EXPIRADA";
export const ACTIVE: SwapStatus[] = ["PENDENTE", "EM_ESPERA"];
