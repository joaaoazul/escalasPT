/**
 * API hook to fetch all users in the station for shift assignment
 */
import { useQuery } from '@tanstack/react-query';
import { fetchUsers } from '../api/users';
import { useAuth } from './useAuth';
import type { User } from '../types';

export function useStationUsers() {
  const { user } = useAuth();
  
  return useQuery({
    queryKey: ['users', 'station', user?.station_id],
    queryFn: async (): Promise<User[]> => {
      if (!user?.station_id) return [];
      const data = await fetchUsers({ station_id: user.station_id, is_active: true, limit: 200 });
      // Usually, 'militar' gets filtered to their own in backend, but Commander gets all
      return data.users;
    },
    enabled: !!user?.station_id && user.role !== 'militar',
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}
