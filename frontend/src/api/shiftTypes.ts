/**
 * Shift Types API functions.
 */

import apiClient from './client';
import type { ShiftType } from '../types';

export interface ShiftTypeListResponse {
  shift_types: ShiftType[];
  total: number;
}

export async function fetchShiftTypes(params: {
  is_active?: boolean;
} = {}): Promise<ShiftTypeListResponse> {
  const response = await apiClient.get<ShiftTypeListResponse>(
    '/shift-types/',
    { params },
  );
  return response.data;
}
