/**
 * WebSocketProvider — live notifications and calendar updates while
 * authenticated.
 *
 * Two transports, picked by /api/realtime/config:
 * - Supabase Realtime, where the API runs as a serverless function (Vercel)
 *   and cannot hold a socket. Its messages are bare signals; the data itself
 *   is fetched from the API, which checks who is asking.
 * - The API's own /ws endpoint, as in the self-hosted (Docker) deployment.
 */

import { useCallback, useEffect, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '../hooks/useAuth';
import { useNotificationStore } from '../store/notificationStore';
import { getAccessToken } from '../api/client';
import { fetchNotifications } from '../api/notifications';
import { fetchRealtimeConfig, type RealtimeConfig } from '../api/realtime';
import type { Notification } from '../types';

type Stop = () => void;

/** What both transports hand to the provider. */
type LiveMessage =
  | { type: 'notification'; data?: NotificationPayload }
  | { type: 'calendar_sync' };

/** /ws sends notification_type; the REST API (the Realtime path) sends type. */
type NotificationPayload = Partial<Notification> & { notification_type?: string };

/* ── Self-hosted: /ws ──────────────────────────────────── */

function connectWebSocket(onMessage: (data: LiveMessage) => void): Stop {
  let stopped = false;
  let socket: WebSocket | null = null;
  let reconnectTimeout: number | null = null;

  const connect = () => {
    if (stopped) return;

    const token = getAccessToken();
    if (!token) return; // No token yet, wait for next cycle

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      socket = ws;

      ws.onopen = () => {
        if (import.meta.env.DEV) console.log('[WebSocket] Connected securely to EscalasPT');
        // Authenticate via first message (token never in URL/logs)
        ws.send(JSON.stringify({ type: 'auth', token }));
        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
          } else {
            onMessage(data);
          }
        } catch (e) {
          if (import.meta.env.DEV) console.error('[WebSocket] Failed to parse message', e);
        }
      };

      ws.onclose = () => {
        if (import.meta.env.DEV) console.log('[WebSocket] Disconnected');
        // Reconnect logic
        if (!stopped) {
          reconnectTimeout = window.setTimeout(connect, 5000); // 5 sec backoff
        }
      };
    } catch (err) {
      if (import.meta.env.DEV) console.error('[WebSocket] Connection error:', err);
    }
  };

  connect();

  return () => {
    stopped = true;
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    socket?.close();
    socket = null;
  };
}

/* ── Serverless: Supabase Realtime ─────────────────────── */

async function connectRealtime(
  config: Extract<RealtimeConfig, { enabled: true }>,
  onMessage: (data: LiveMessage) => void,
): Promise<Stop> {
  // Loaded only here, so the self-hosted build never downloads it.
  const { RealtimeClient } = await import('@supabase/realtime-js');

  // Notifications the user has already been shown. A signal only says "you
  // have something new", so the unread list is fetched and whatever is not
  // in here is what the signal was about.
  const seen = new Set<string>();
  try {
    const initial = await fetchNotifications({ unread_only: true, limit: 50 });
    initial.notifications.forEach((n) => seen.add(n.id));
  } catch {
    // Worst case, the first signal toasts a few older unread notifications.
  }

  let fetching: Promise<void> | null = null;
  const pullNotifications = () => {
    // Several signals in a burst (a whole schedule published) need one fetch.
    fetching ??= fetchNotifications({ unread_only: true, limit: 20 })
      .then(({ notifications }) => {
        notifications
          .filter((n) => !seen.has(n.id))
          .reverse() // oldest first, so the newest toast ends up on top
          .forEach((n) => {
            seen.add(n.id);
            onMessage({ type: 'notification', data: n });
          });
      })
      .catch((e) => {
        if (import.meta.env.DEV) console.error('[Realtime] Failed to fetch notifications', e);
      })
      .finally(() => {
        fetching = null;
      });
  };

  const client = new RealtimeClient(`${config.url}/realtime/v1`, {
    params: { apikey: config.key },
  });

  const channels = config.channels.map((topic) =>
    client
      .channel(topic)
      .on('broadcast', { event: 'notification' }, pullNotifications)
      .on('broadcast', { event: 'calendar_sync' }, () => onMessage({ type: 'calendar_sync' }))
      .subscribe((status, err) => {
        if (import.meta.env.DEV) console.log(`[Realtime] ${topic}: ${status}`, err ?? '');
      }),
  );

  return () => {
    channels.forEach((channel) => client.removeChannel(channel));
    client.disconnect();
  };
}

/* ── Provider ──────────────────────────────────────────── */

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { addNotification } = useNotificationStore();
  const queryClient = useQueryClient();

  const handleMessage = useCallback((data: LiveMessage) => {
    if (data.type === 'notification') {
      const notification = data.data;
      if (!notification) return;
      addNotification(notification as Notification);

      // Route to semantic toast based on notification_type
      const type: string = notification.notification_type ?? notification.type ?? '';
      const title: string = notification.title ?? '';
      const description: string = notification.message ?? '';
      const opts = { description, duration: 6000 };

      if (type === 'shift_cancelled') {
        toast.error(title, opts);
        queryClient.invalidateQueries({ queryKey: ['shifts'] });
      } else if (type === 'shift_updated') {
        toast.warning(title, opts);
        queryClient.invalidateQueries({ queryKey: ['shifts'] });
      } else if (type === 'swap_rejected') {
        toast.error(title, opts);
        queryClient.invalidateQueries({ queryKey: ['swaps'] });
      } else if (type === 'swap_requested') {
        toast.warning(title, opts);
        queryClient.invalidateQueries({ queryKey: ['swaps'] });
      } else if (type === 'shift_published' || type === 'swap_accepted' || type === 'swap_approved') {
        toast.success(title, opts);
        queryClient.invalidateQueries({ queryKey: ['shifts'] });
        queryClient.invalidateQueries({ queryKey: ['swaps'] });
      } else {
        toast.info(title, opts);
      }
    } else if (data.type === 'calendar_sync') {
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
      queryClient.invalidateQueries({ queryKey: ['swaps'] });
    }
  }, [addNotification, queryClient]);

  useEffect(() => {
    if (!isAuthenticated) return;

    let cancelled = false;
    let stop: Stop | null = null;

    (async () => {
      let config: RealtimeConfig = { enabled: false };
      try {
        config = await fetchRealtimeConfig();
      } catch {
        // An API without /realtime/config is an older self-hosted one: /ws.
      }
      if (cancelled) return;

      const started = config.enabled
        ? await connectRealtime(config, handleMessage)
        : connectWebSocket(handleMessage);

      // Logged out or unmounted while connecting: undo it straight away.
      if (cancelled) started();
      else stop = started;
    })().catch((err) => {
      if (import.meta.env.DEV) console.error('[Realtime] Connection error:', err);
    });

    return () => {
      cancelled = true;
      stop?.();
    };
  }, [isAuthenticated, handleMessage]);

  return <>{children}</>;
}
