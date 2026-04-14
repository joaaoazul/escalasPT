/**
 * Shifts API functions.
 */

import apiClient from './client';
import type {
  Shift,
  ShiftCreateResponse,
  ShiftListResponse,
  ShiftPublishResponse,
  ShiftValidateResponse,
} from '../types';

export interface ShiftFilters {
  station_id?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
  status?: string;
  skip?: number;
  limit?: number;
}

export async function fetchShifts(
  filters: ShiftFilters = {},
): Promise<ShiftListResponse> {
  const response = await apiClient.get<ShiftListResponse>('/shifts/', {
    params: filters,
  });
  return response.data;
}

export async function fetchShift(shiftId: string): Promise<Shift> {
  const response = await apiClient.get<Shift>(`/shifts/${shiftId}`);
  return response.data;
}

export interface ShiftCreateData {
  user_id: string;
  shift_type_id?: string;
  date: string;
  start_datetime: string;
  end_datetime: string;
  notes?: string;
  location?: string;
  grat_type?: string;
}

export async function createShift(
  data: ShiftCreateData,
): Promise<ShiftCreateResponse> {
  const response = await apiClient.post<ShiftCreateResponse>('/shifts/', data);
  return response.data;
}

export interface ShiftUpdateData {
  shift_type_id?: string;
  date?: string;
  start_datetime?: string;
  end_datetime?: string;
  notes?: string;
}

export async function updateShift(
  shiftId: string,
  data: ShiftUpdateData,
): Promise<ShiftCreateResponse> {
  const response = await apiClient.put<ShiftCreateResponse>(
    `/shifts/${shiftId}`,
    data,
  );
  return response.data;
}

export async function deleteShift(shiftId: string): Promise<void> {
  await apiClient.delete(`/shifts/${shiftId}`);
}

export async function publishShifts(
  shiftIds: string[],
): Promise<ShiftPublishResponse> {
  const response = await apiClient.post<ShiftPublishResponse>(
    '/shifts/publish',
    { shift_ids: shiftIds },
  );
  return response.data;
}

export async function validateShifts(
  shiftIds: string[],
): Promise<ShiftValidateResponse> {
  const response = await apiClient.post<ShiftValidateResponse>(
    '/shifts/validate',
    { shift_ids: shiftIds },
  );
  return response.data;
}
