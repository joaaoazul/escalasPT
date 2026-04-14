/**
 * useStationSchedule — fetches all shifts for the user's station in a given month.
 * Pre-fetches the next month for smooth navigation.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { addMonths, format, startOfMonth, endOfMonth } from 'date-fns';
import { fetchShifts } from '../api/shifts';
import { useAuth } from './useAuth';
import type { Shift } from '../types';

function getMonthRange(date: Date) {
  const start = startOfMonth(date);
  const end = endOfMonth(date);
  return {
    date_from: format(start, 'yyyy-MM-dd'),
    date_to: format(end, 'yyyy-MM-dd'),
  };
}

export function useStationSchedule(currentMonth: Date) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { date_from, date_to } = getMonthRange(currentMonth);

  const queryKey = ['shifts', 'station', date_from, date_to] as const;

  const query = useQuery({
    queryKey,
    queryFn: async (): Promise<Shift[]> => {
      if (!user?.station_id) return [];
      const response = await fetchShifts({
        station_id: user.station_id ?? undefined,
        date_from,
        date_to,
        limit: 500,
      });
      return response.shifts;
    },
    enabled: !!user?.station_id,
    staleTime: 1000 * 60 * 5,
  });

  // Pre-fetch next month
  useEffect(() => {
    if (!user?.station_id) return;
    const nextMonth = addMonths(currentMonth, 1);
    const next = getMonthRange(nextMonth);

    queryClient.prefetchQuery({
      queryKey: ['shifts', 'station', next.date_from, next.date_to],
      queryFn: async () => {
        const response = await fetchShifts({
          station_id: user.station_id ?? undefined,
          date_from: next.date_from,
          date_to: next.date_to,
          limit: 500,
        });
        return response.shifts;
      },
      staleTime: 1000 * 60 * 5,
    });
  }, [currentMonth, user, queryClient]);

  return query;
}
