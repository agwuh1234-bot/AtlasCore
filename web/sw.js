const CACHE_NAME = 'atlas-app-v21-20260827';
const LEGACY_CACHE_PREFIX = 'atlas-app-';
const SHELL = [
  '/',
  '/app/',
  '/app/manifest.json',
  '/app/icon.svg',
  '/app/projects.css',
  '/app/shell.css',
  '/app/projects.js',
  '/app/files.js',
  '/app/recovery.js',
  '/app/control_center.js',
  '/app/push.js',
  '/app/app.js',
  '/app/ux.js',
  '/app/status.js',
  '/app/format.js',
  '/app/shell.js',
  '/app/runtime-refresh.js',
];

function isApiPath(pathname) {
  return pathname === '/health'
    || pathname === '/task'
    || pathname === '/bridge'
    || pathname.startsWith('/app-')
    || pathname.startsWith('/integrations/')
    || pathname === '/mcp'
    || pathname.startsWith('/mcp/');
}

async function fetchFresh(request) {
  return fetch(new Request(request, { cache: 'no-store' }));
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.allSettled(SHELL.map(async (url) => {
      const response = await fetch(url, { cache: 'no-store' });
      if (response.ok) await cache.put(url, response.clone());
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    const hadLegacyCache = keys.some((key) => key.startsWith(LEGACY_CACHE_PREFIX) && key !== CACHE_NAME);
    await Promise.all(keys
      .filter((key) => key.startsWith(LEGACY_CACHE_PREFIX) && key !== CACHE_NAME)
      .map((key) => caches.delete(key)));
    await self.clients.claim();

    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    await Promise.allSettled(windows.map(async (client) => {
      client.postMessage({ type: 'ATLAS_SW_UPDATED', version: CACHE_NAME });
      // One-time migration from the old stale-cache worker. This makes an
      // already-open installed PWA pick up the current app shell immediately.
      if (hadLegacyCache && client.navigate) await client.navigate(client.url);
    }));
  })());
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
  if (event.data?.type === 'CLEAR_ATLAS_CACHE') {
    event.waitUntil(caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith(LEGACY_CACHE_PREFIX)).map((key) => caches.delete(key))
    )));
  }
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // Never cache or rewrite authenticated/API traffic. In particular, the
  // service worker must not change allow_writes on Atlas jobs.
  if (event.request.method !== 'GET' || isApiPath(url.pathname)) {
    if (event.request.method === 'GET' && isApiPath(url.pathname)) {
      event.respondWith(fetchFresh(event.request));
    }
    return;
  }

  event.respondWith((async () => {
    try {
      const response = await fetchFresh(event.request);
      if (response && response.ok && response.type !== 'opaque') {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(event.request, response.clone());
      }
      return response;
    } catch (error) {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      if (event.request.mode === 'navigate') {
        return (await caches.match('/')) || (await caches.match('/app/')) || Promise.reject(error);
      }
      throw error;
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
