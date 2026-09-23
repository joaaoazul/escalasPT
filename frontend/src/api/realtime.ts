/**
 * Where to listen for live updates — see backend/app/services/realtime.py.
 */

import apiClient from './client';

export type RealtimeConfig =
  | { enabled: false }
  | { enabled: true; url: string; key: string; channels: string[] };

export async function fetchRealtimeConfig(): Promise<RealtimeConfig> {
  const response = await apiClient.get<RealtimeConfig>('/realtime/config');
  return response.data;
}
