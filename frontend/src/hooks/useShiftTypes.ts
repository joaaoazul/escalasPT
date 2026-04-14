/**
 * useShiftTypes — fetches active shift types for the user's station.
 */

import { useQuery } from '@tanstack/react-query';
import { fetchShiftTypes } from '../api/shiftTypes';
import { useAuth } from './useAuth';
import type { ShiftType } from '../types';

export function useShiftTypes() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['shiftTypes'],
    queryFn: async (): Promise<ShiftType[]> => {
      const response = await fetchShiftTypes({ is_active: true });
      return response.shift_types;
    },
    enabled: !!user && user.role !== 'admin',
    staleTime: 1000 * 60 * 30, // 30 min — shift types rarely change
  });
}
