const CACHE_NAME = 'atlas-app-v20';
const ASSETS = ['/', '/app/manifest.json', '/app/styles.css', '/app/projects.css', '/app/format.css', '/app/shell.css', '/app/projects.js', '/app/files.js', '/app/control_center.js', '/app/push.js', '/app/app.js', '/app/ux.js', '/app/status.js', '/app/format.js', '/app/recovery.js', '/app/shell.js', '/app/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith('atlas-app-') && key !== CACHE_NAME).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith((async () => {
    try {
      const response = await fetch(event.request);
      if (response && response.ok) {
        const cache = await caches.open(CACHE_NAME);
        cache.put(event.request, response.clone());
      }
      return response;
    } catch {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      if (event.request.mode === 'navigate') return caches.match('/');
      throw new Error('offline');
    }
  })());
});

self.addEventListener('push', (event) => {
  let payload = { title: 'Atlas', body: 'Задача выполнена', url: '/' };
  try {
    if (event.data) payload = Object.assign(payload, event.data.json());
  } catch {
    if (event.data) payload.body = event.data.text();
  }
  event.waitUntil(self.registration.showNotification(payload.title || 'Atlas', {
    body: payload.body || 'Задача выполнена',
    icon: '/app/icon.svg',
    badge: '/app/icon.svg',
    tag: payload.tag || 'atlas-done',
    data: { url: payload.url || '/' },
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      const target = (event.notification.data && event.notification.data.url) || '/';
      if (list.length > 0) {
        const client = list[0];
        return client.focus().then(() => client.navigate ? client.navigate(target) : client);
      }
      return clients.openWindow(target);
    })
  );
});