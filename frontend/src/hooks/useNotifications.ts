/**
 * useNotifications — React Query hook for handling notifications.
 * Automatically synchronizes with Zustand notificationStore.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { fetchNotifications, markNotificationsRead } from '../api/notifications';
import { useNotificationStore } from '../store/notificationStore';
import { useAuth } from './useAuth';
import type { NotificationListResponse } from '../types';

export function useNotifications() {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const { setNotifications, markAsRead: setStoreRead } = useNotificationStore();

  const query = useQuery({
    queryKey: ['notifications'],
    queryFn: async (): Promise<NotificationListResponse> => {
      const response = await fetchNotifications({ limit: 100 });
      return response;
    },
    enabled: isAuthenticated,
    staleTime: 1000 * 60 * 60, // 1 hour, WebSockets will handle live updates
  });

  // Sync initial query with Zustand store
  useEffect(() => {
    if (query.data) {
      setNotifications(query.data.notifications, query.data.unread_count);
    }
  }, [query.data, setNotifications]);

  const markReadMutation = useMutation({
    mutationFn: (ids: string[]) => markNotificationsRead(ids),
    onSuccess: (_, ids) => {
      // Optimistically update store
      setStoreRead(ids);
      // Invalidate to eventually sync with DB
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  return {
    ...query,
    markAsRead: markReadMutation.mutate,
    isMarkingRead: markReadMutation.isPending,
  };
}
