/**
 * usePersonalSchedule — fetches the current user's shifts for a given month.
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

export function usePersonalSchedule(currentMonth: Date) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { date_from, date_to } = getMonthRange(currentMonth);

  const queryKey = ['shifts', 'personal', date_from, date_to] as const;

  const query = useQuery({
    queryKey,
    queryFn: async (): Promise<Shift[]> => {
      if (!user) return [];
      const response = await fetchShifts({
        user_id: user.id,
        date_from,
        date_to,
        status: user.role === 'militar' ? 'published' : undefined,
      });
      return response.shifts;
    },
    enabled: !!user,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Pre-fetch next month
  useEffect(() => {
    if (!user) return;
    const nextMonth = addMonths(currentMonth, 1);
    const next = getMonthRange(nextMonth);

    queryClient.prefetchQuery({
      queryKey: ['shifts', 'personal', next.date_from, next.date_to],
      queryFn: async () => {
        const response = await fetchShifts({
          user_id: user.id,
          date_from: next.date_from,
          date_to: next.date_to,
          status: user.role === 'militar' ? 'published' : undefined,
        });
        return response.shifts;
      },
      staleTime: 1000 * 60 * 5,
    });
  }, [currentMonth, user, queryClient]);

  return query;
}
