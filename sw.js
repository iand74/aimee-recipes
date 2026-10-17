/* Service worker: makes the app work offline and pick up updates.
   Bump VERSION whenever you push a change (keep it in step with APP_VERSION in app.js). */
const VERSION = '1.2.0';
const CACHE = 'aimee-recipes-' + VERSION;
const SHELL = [
  './', 'index.html', 'styles.css', 'app.js', 'manifest.webmanifest',
  'icons/icon-96.png', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' })))));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith('aimee-recipes-') && k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

// Network first (so updates show up straight away), cache when offline.
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith((async () => {
    try {
      const fresh = await fetch(req, { cache: 'no-cache' });
      if (fresh.ok) { const c = await caches.open(CACHE); c.put(req, fresh.clone()); }
      return fresh;
    } catch {
      const cached = await caches.match(req, { ignoreSearch: true });
      return cached || (req.mode === 'navigate' ? caches.match('index.html') : Response.error());
    }
  })());
});
