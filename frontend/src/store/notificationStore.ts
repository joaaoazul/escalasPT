/**
 * Notification store — Zustand.
 * Global notification state with unread counter.
 */

import { create } from 'zustand';
import type { Notification } from '../types';

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  setNotifications: (notifications: Notification[], unreadCount: number) => void;
  addNotification: (notification: Notification) => void;
  markAsRead: (ids: string[]) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  unreadCount: 0,

  setNotifications: (notifications, unreadCount) => {
    set({ notifications, unreadCount });
  },

  addNotification: (notification) => {
    set((state) => ({
      notifications: [notification, ...state.notifications],
      unreadCount: state.unreadCount + 1,
    }));
  },

  markAsRead: (ids) => {
    set((state) => {
      const idSet = new Set(ids);
      const updated = state.notifications.map((n) =>
        idSet.has(n.id) ? { ...n, is_read: true } : n,
      );
      const newUnread = updated.filter((n) => !n.is_read).length;
      return { notifications: updated, unreadCount: newUnread };
    });
  },

  clearAll: () => {
    set({ notifications: [], unreadCount: 0 });
  },
}));
