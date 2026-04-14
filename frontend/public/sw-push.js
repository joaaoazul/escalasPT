// EscalasPT — Push notification service worker
// This file is loaded by the browser for Web Push events

self.addEventListener('push', (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'EscalasPT', body: event.data.text() };
  }

  const title = payload.title || 'EscalasPT';
  const options = {
    body: payload.body || '',
    icon: '/shield.svg',
    badge: '/shield.svg',
    tag: payload.type || 'general',
    renotify: true,
    data: payload.data || {},
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus existing window or open new one
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow('/');
    })
  );
});
