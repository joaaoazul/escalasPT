/**
 * WebSocketProvider — manages a persistent WebSocket connection 
 * for live notifications when authenticated.
 */

import { useEffect, useRef, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '../hooks/useAuth';
import { useNotificationStore } from '../store/notificationStore';
import { getAccessToken } from '../api/client';

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { addNotification } = useNotificationStore();
  const queryClient = useQueryClient();
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
      return;
    }

    let isMounted = true;

    const connect = () => {
      if (!isMounted) return;

      const token = getAccessToken();
      if (!token) return; // No token yet, wait for next cycle

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws`;
      
      try {
        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => {
          console.log('[WebSocket] Connected securely to EscalasPT');
          // Authenticate via first message (token never in URL/logs)
          ws.current?.send(JSON.stringify({ type: 'auth', token }));
          if (reconnectTimeout.current) {
            clearTimeout(reconnectTimeout.current);
            reconnectTimeout.current = null;
          }
        };

        ws.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'notification') {
              const notification = data.data;
              if (!notification) return;
              addNotification(notification);

              // Route to semantic toast based on notification_type
              const type: string = notification.notification_type ?? '';
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
            } else if (data.type === 'ping') {
              ws.current?.send(JSON.stringify({ type: 'pong' }));
            }
          } catch (e) {
            console.error('[WebSocket] Failed to parse message', e);
          }
        };

        ws.current.onclose = () => {
          console.log('[WebSocket] Disconnected');
          // Reconnect logic
          if (isMounted && isAuthenticated) {
            reconnectTimeout.current = window.setTimeout(connect, 5000); // 5 sec backoff
          }
        };

      } catch (err) {
        console.error('[WebSocket] Connection error:', err);
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
    };
  }, [isAuthenticated, addNotification]);

  return <>{children}</>;
}
