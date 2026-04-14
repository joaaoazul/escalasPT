/**
 * Notifications API functions.
 */

import apiClient from './client';
import type { NotificationListResponse } from '../types';

export async function fetchNotifications(params: {
  unread_only?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<NotificationListResponse> {
  const response = await apiClient.get<NotificationListResponse>(
    '/notifications/',
    { params },
  );
  return response.data;
}

export async function markNotificationsRead(
  notificationIds: string[],
): Promise<{ updated: number }> {
  const response = await apiClient.post<{ updated: number }>(
    '/notifications/read',
    { notification_ids: notificationIds },
  );
  return response.data;
}

// ── Push Subscription ────────────────────────────────────

export async function getVapidPublicKey(): Promise<{
  vapid_public_key: string;
  push_enabled: boolean;
}> {
  const response = await apiClient.get('/notifications/push/vapid-key');
  return response.data;
}

export async function subscribePush(subscription: PushSubscription): Promise<void> {
  const json = subscription.toJSON();
  await apiClient.post('/notifications/push/subscribe', {
    endpoint: json.endpoint,
    keys: json.keys,
  });
}

export async function unsubscribePush(endpoint: string): Promise<void> {
  await apiClient.post('/notifications/push/unsubscribe', { endpoint });
}
