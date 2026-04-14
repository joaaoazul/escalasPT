/**
 * Admin API functions — system stats, audit logs, sessions, password reset.
 */

import apiClient from './client';

/* ── System Stats ───────────────────────────────────────── */

export interface SystemStats {
  total_users: number;
  active_users: number;
  inactive_users: number;
  total_stations: number;
  active_stations: number;
  total_shifts: number;
  published_shifts: number;
  draft_shifts: number;
  active_sessions: number;
  users_by_role: Record<string, number>;
  shifts_last_30_days: number;
}

export async function fetchSystemStats(): Promise<SystemStats> {
  const response = await apiClient.get<SystemStats>('/admin/stats');
  return response.data;
}

/* ── Audit Logs ─────────────────────────────────────────── */

export interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  old_data: Record<string, unknown> | null;
  new_data: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogFilters {
  action?: string;
  resource_type?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export interface AuditLogListResponse {
  logs: AuditLog[];
  total: number;
}

export async function fetchAuditLogs(
  filters: AuditLogFilters = {},
): Promise<AuditLogListResponse> {
  const response = await apiClient.get<AuditLogListResponse>('/admin/audit-logs', {
    params: filters,
  });
  return response.data;
}

/* ── Password Reset ─────────────────────────────────────── */

export async function adminResetPassword(
  userId: string,
  newPassword: string,
): Promise<void> {
  await apiClient.post(`/admin/users/${userId}/reset-password`, {
    new_password: newPassword,
  });
}

/* ── Session Management ─────────────────────────────────── */

export interface ActiveSession {
  id: string;
  user_id: string;
  session_id: string;
  ip_address: string | null;
  user_agent: string | null;
  is_revoked: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface SessionListResponse {
  sessions: ActiveSession[];
  total: number;
}

export async function fetchSessions(params: {
  user_id?: string;
  active_only?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<SessionListResponse> {
  const response = await apiClient.get<SessionListResponse>('/admin/sessions', {
    params,
  });
  return response.data;
}

export async function revokeSession(sessionId: string): Promise<void> {
  await apiClient.post(`/admin/sessions/${sessionId}/revoke`);
}

export async function revokeAllUserSessions(userId: string): Promise<void> {
  await apiClient.post(`/admin/users/${userId}/revoke-all-sessions`);
}

/* ── User Actions ───────────────────────────────────────── */

export async function unlockUser(userId: string): Promise<void> {
  await apiClient.post(`/admin/users/${userId}/unlock`);
}

/* ── Station Onboarding ─────────────────────────────────── */

export interface StationOnboardRequest {
  station_name: string;
  station_code: string;
  station_address?: string;
  station_phone?: string;
  comandante_username: string;
  comandante_email: string;
  comandante_password: string;
  comandante_full_name: string;
  comandante_nip: string;
  comandante_phone?: string;
}

export interface StationOnboardResponse {
  station_id: string;
  station_name: string;
  comandante_id: string;
  comandante_username: string;
}

export async function onboardStation(
  data: StationOnboardRequest,
): Promise<StationOnboardResponse> {
  const response = await apiClient.post<StationOnboardResponse>(
    '/admin/onboard-station',
    data,
  );
  return response.data;
}
