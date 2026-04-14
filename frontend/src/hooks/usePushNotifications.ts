/**
 * Hook for managing Web Push notification subscriptions.
 */

import { useCallback, useEffect, useState } from 'react';
import { getVapidPublicKey, subscribePush, unsubscribePush } from '../api/notifications';
import { useAuthStore } from '../store/authStore';

type PushState = 'loading' | 'unsupported' | 'denied' | 'prompt' | 'subscribed' | 'unsubscribed' | 'disabled';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function usePushNotifications() {
  const [state, setState] = useState<PushState>('loading');
  const [vapidKey, setVapidKey] = useState<string>('');
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) return;

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setState('unsupported');
      return;
    }

    const init = async () => {
      try {
        const { vapid_public_key, push_enabled } = await getVapidPublicKey();
        if (!push_enabled || !vapid_public_key) {
          setState('disabled');
          return;
        }
        setVapidKey(vapid_public_key);

        const permission = Notification.permission;
        if (permission === 'denied') {
          setState('denied');
          return;
        }

        // Register push service worker
        const registration = await navigator.serviceWorker.register('/sw-push.js');
        const existing = await registration.pushManager.getSubscription();

        if (existing) {
          setState('subscribed');
        } else if (permission === 'granted') {
          setState('unsubscribed');
        } else {
          setState('prompt');
        }
      } catch {
        setState('disabled');
      }
    };

    init();
  }, [isAuthenticated]);

  const subscribe = useCallback(async () => {
    if (!vapidKey) return false;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setState('denied');
        return false;
      }

      const registration = await navigator.serviceWorker.register('/sw-push.js');
      await navigator.serviceWorker.ready;

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });

      await subscribePush(subscription);
      setState('subscribed');
      return true;
    } catch (err) {
      console.error('Push subscription failed:', err);
      return false;
    }
  }, [vapidKey]);

  const unsubscribe = useCallback(async () => {
    try {
      const registration = await navigator.serviceWorker.getRegistration('/sw-push.js');
      if (registration) {
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await unsubscribePush(subscription.endpoint);
          await subscription.unsubscribe();
        }
      }
      setState('unsubscribed');
      return true;
    } catch {
      return false;
    }
  }, []);

  return { state, subscribe, unsubscribe };
}
