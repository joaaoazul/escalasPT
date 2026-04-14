/* ============================================================
   TypeScript interfaces — single source of truth
   ============================================================ */

export type UserRole = 'admin' | 'comandante' | 'adjunto' | 'secretaria' | 'militar';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  nip: string;
  numero_ordem: string | null;
  role: UserRole;
  station_id: string | null;
  phone: string | null;
  default_shift_type_id: string | null;
  totp_enabled: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Station {
  id: string;
  name: string;
  code: string;
  address: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type ShiftStatus = 'draft' | 'published' | 'cancelled';

export interface Shift {
  id: string;
  user_id: string;
  station_id: string;
  shift_type_id: string | null;
  date: string;
  start_datetime: string;
  end_datetime: string;
  status: ShiftStatus;
  notes: string | null;
  location: string | null;
  grat_type: string | null;
  created_by: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  user_name: string | null;
  user_numero_ordem: string | null;
  shift_type_name: string | null;
  shift_type_code: string | null;
  shift_type_color: string | null;
}

export interface ShiftType {
  id: string;
  station_id: string;
  name: string;
  code: string;
  description: string | null;
  start_time: string;
  end_time: string;
  color: string;
  min_staff: number;
  is_absence: boolean;
  fixed_slots: boolean;
  is_active: boolean;
}

export type SwapStatus = 'pending_target' | 'pending_approval' | 'approved' | 'rejected' | 'cancelled';

export interface SwapShiftSummary {
  id: string;
  date: string;
  start_datetime: string | null;
  end_datetime: string | null;
  shift_type_code: string | null;
  shift_type_color: string | null;
  shift_type_name: string | null;
  user_id: string;
  user_name: string | null;
}

export interface ShiftSwapRequest {
  id: string;
  requester_shift_id: string;
  target_shift_id: string;
  requester_id: string;
  target_id: string;
  status: SwapStatus;
  reason: string | null;
  responded_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  /** Populated when fetched from the API */
  requester_shift?: SwapShiftSummary;
  target_shift?: SwapShiftSummary;
}

export type NotificationType =
  | 'shift_published'
  | 'shift_updated'
  | 'shift_cancelled'
  | 'swap_requested'
  | 'swap_accepted'
  | 'swap_approved'
  | 'swap_rejected'
  | 'general';

export interface Notification {
  id: string;
  user_id: string;
  station_id: string;
  type: NotificationType;
  title: string;
  message: string;
  is_read: boolean;
  data: Record<string, unknown> | null;
  created_at: string;
}

/** Shape of each entry in `data.shifts` for shift_published notifications. */
export interface NotificationShiftEntry {
  date: string;
  shift_type_code: string;
  shift_type_color: string;
  shift_type_name: string;
}

export interface ConflictDetail {
  shift_id: string;
  user_id: string;
  user_name: string;
  conflict_type: 'overlap' | 'min_rest' | 'warning';
  description: string;
  severity: 'error' | 'warning';
}

/* ── API Response Wrappers ──────────────────────────────── */

export interface LoginResponse {
  access_token: string;
  token_type: string;
  requires_totp: boolean;
}

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  nip: string;
  role: UserRole;
  station_id: string | null;
  totp_enabled: boolean;
  is_active: boolean;
}

export interface ShiftListResponse {
  shifts: Shift[];
  total: number;
}

export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
}

export interface ShiftPublishResponse {
  published_count: number;
  conflicts: ConflictDetail[];
  message: string;
}

export interface ShiftValidateResponse {
  valid: boolean;
  conflicts: ConflictDetail[];
}

export interface ShiftCreateResponse {
  shift: Shift;
  warnings: ConflictDetail[];
}
