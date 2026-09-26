"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "./api/client";
import type { Invite, InvitePreview, Me, Membership, Posto, Shift, ShiftType, Swap, Warning } from "./api/models";

export const qk = {
  me: ["me"] as const,
  membership: ["membership"] as const,
  posto: (id: string) => ["posto", id] as const,
  types: (postoId: string) => ["types", postoId] as const,
  myShifts: (from: string, to: string) => ["shifts", "me", from, to] as const,
  postoShifts: (postoId: string, from: string, to: string, groupId?: string) => ["shifts", "posto", postoId, from, to, groupId ?? "all"] as const,
  userShifts: (userId: string, from: string, to: string) => ["shifts", "user", userId, from, to] as const,
  swaps: (box: string) => ["swaps", box] as const,
  invites: (groupId: string) => ["invites", groupId] as const,
};

export function useMe() {
  return useQuery({ queryKey: qk.me, queryFn: () => unwrap<Me>(api.GET("/api/v1/me") as never), retry: false, staleTime: 60_000 });
}

/** null = o militar ainda não pertence a um grupo de folgas. */
export function useMembership(enabled = true) {
  return useQuery({
    queryKey: qk.membership,
    enabled,
    queryFn: async () => {
      try {
        return await unwrap<Membership>(api.GET("/api/v1/me/membership") as never);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
  });
}

export function usePosto(id: string | undefined) {
  return useQuery({
    queryKey: qk.posto(id ?? "-"),
    enabled: !!id,
    queryFn: () => unwrap<Posto>(api.GET("/api/v1/postos/{postoId}", { params: { path: { postoId: id! } } }) as never),
  });
}

export function useShiftTypes(postoId: string | undefined) {
  return useQuery({
    queryKey: qk.types(postoId ?? "-"),
    enabled: !!postoId,
    staleTime: 10 * 60_000,
    queryFn: () => unwrap<ShiftType[]>(api.GET("/api/v1/postos/{postoId}/shift-types", { params: { path: { postoId: postoId! } } }) as never),
  });
}

export function useMyShifts(from: string, to: string) {
  return useQuery({
    queryKey: qk.myShifts(from, to),
    queryFn: () => unwrap<Shift[]>(api.GET("/api/v1/me/shifts", { params: { query: { from, to } } }) as never),
    placeholderData: (prev) => prev,
  });
}

export function usePostoShifts(postoId: string | undefined, from: string, to: string, groupId?: string) {
  return useQuery({
    queryKey: qk.postoShifts(postoId ?? "-", from, to, groupId),
    enabled: !!postoId,
    queryFn: () =>
      unwrap<Shift[]>(api.GET("/api/v1/postos/{postoId}/shifts", { params: { path: { postoId: postoId! }, query: { from, to, groupId } } }) as never),
    placeholderData: (prev) => prev,
  });
}

export function useUserShifts(userId: string | undefined, from: string, to: string) {
  return useQuery({
    queryKey: qk.userShifts(userId ?? "-", from, to),
    enabled: !!userId,
    queryFn: () => unwrap<Shift[]>(api.GET("/api/v1/users/{userId}/shifts", { params: { path: { userId: userId! }, query: { from, to } } }) as never),
  });
}

export function useSwaps(box: "received" | "sent" | "history") {
  return useQuery({
    queryKey: qk.swaps(box),
    queryFn: () => unwrap<Swap[]>(api.GET("/api/v1/me/swaps", { params: { query: { box } } }) as never),
    refetchInterval: 30_000,
  });
}

export function useInvites(groupId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.invites(groupId ?? "-"),
    enabled: !!groupId && enabled,
    queryFn: () => unwrap<Invite[]>(api.GET("/api/v1/groups/{groupId}/invites", { params: { path: { groupId: groupId! } } }) as never),
  });
}

export function useInvitePreview(code: string) {
  return useQuery({
    queryKey: ["invite", code],
    retry: false,
    queryFn: () => unwrap<InvitePreview>(api.GET("/api/v1/invites/{code}", { params: { path: { code } } }) as never),
  });
}

// ── escrita ──

export type WriteResult = { shifts: Shift[]; warnings: Warning[] };

export function usePaint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { shiftTypeId: string | null; dates: string[] }) =>
      unwrap<WriteResult>(api.PUT("/api/v1/me/shifts/paint", { body: { shiftTypeId: v.shiftTypeId as string, dates: v.dates } }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: ["shifts"] }),
  });
}

export function useAddShift() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { shiftTypeId: string; date: string; start?: string; durationMinutes?: number; notes?: string }) =>
      unwrap<WriteResult>(api.POST("/api/v1/me/shifts", { body: v as never }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: ["shifts"] }),
  });
}

export function useDeleteShift() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unwrap<void>(api.DELETE("/api/v1/shifts/{id}", { params: { path: { id } } }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: ["shifts"] }),
  });
}

export function useUpdateNotes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; version: number; notes: string }) =>
      unwrap<Shift>(api.PATCH("/api/v1/shifts/{id}", { params: { path: { id: v.id } }, body: { version: v.version, notes: v.notes } }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: ["shifts"] }),
  });
}

export function useRequestSwap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { shiftId: string; targetShiftId: string; message?: string }) =>
      unwrap<Swap & { warnings: Warning[] }>(api.POST("/api/v1/swaps", { body: v }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: ["swaps"] }),
  });
}

export type SwapAction = "accept" | "hold" | "decline" | "cancel";

export function useSwapAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; action: SwapAction; message?: string }) => {
      const path = { params: { path: { id: v.id } } };
      const body = v.message ? { body: { message: v.message } } : {};
      const call =
        v.action === "accept" ? api.POST("/api/v1/swaps/{id}/accept", path)
        : v.action === "hold" ? api.POST("/api/v1/swaps/{id}/hold", { ...path, ...body } as never)
        : v.action === "decline" ? api.POST("/api/v1/swaps/{id}/decline", { ...path, ...body } as never)
        : api.POST("/api/v1/swaps/{id}/cancel", path);
      return unwrap<Swap>(call as never);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["swaps"] });
      qc.invalidateQueries({ queryKey: ["shifts"] });
    },
  });
}

export function useCreateInvite(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { email?: string; name?: string; rank?: string; role?: string }) =>
      unwrap<{ id: string; code: string; expiresAt: string }>(api.POST("/api/v1/groups/{groupId}/invites", { params: { path: { groupId } }, body: v }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: qk.invites(groupId) }),
  });
}

export function useRevokeInvite(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) =>
      unwrap<void>(api.DELETE("/api/v1/groups/{groupId}/invites/{inviteId}", { params: { path: { groupId, inviteId } } }) as never),
    onSettled: () => qc.invalidateQueries({ queryKey: qk.invites(groupId) }),
  });
}

export function useRemoveMember(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      unwrap<void>(api.DELETE("/api/v1/groups/{groupId}/members/{userId}", { params: { path: { groupId, userId } } }) as never),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["posto"] });
      qc.invalidateQueries({ queryKey: qk.membership });
    },
  });
}

export function useAcceptInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => unwrap<Membership>(api.POST("/api/v1/invites/{code}/accept", { params: { path: { code } } }) as never),
    onSuccess: () => qc.invalidateQueries(),
  });
}
