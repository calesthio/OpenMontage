/* =============================================================
   Service worker — makes the site load instantly and work offline.
   Deliberately conservative so it can never serve stale fares:

     • HTML  → network FIRST (always the freshest prices/phone)
     • assets → cache first (icons, QR codes, fonts, photos)

   If the network is down, the cached copy is served so a customer
   can still see the phone number and book by call/WhatsApp.
   ============================================================= */

const VERSION = 'a1-v1';
const RUNTIME = 'a1-runtime-v1';

// The page itself — cached so an offline visitor still sees everything
const PRECACHE = ['./', './index.html', './404.html', './manifest.webmanifest',
                  './assets/icon-192.png', './assets/icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(PRECACHE).catch(() => undefined))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== VERSION && k !== RUNTIME).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const isDocument = req.mode === 'navigate' ||
                     (req.headers.get('accept') || '').includes('text/html');

  // ---- HTML: network first, fall back to cache when offline ----
  if (isDocument) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => undefined);
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
    );
    return;
  }

  // ---- Everything else (icons, QR codes, photos, fonts): cache first ----
  event.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((res) => {
        // only cache successful, same-origin-safe responses
        if (res && res.status === 200 && (url.protocol === 'https:' || url.protocol === 'http:')) {
          const copy = res.clone();
          caches.open(RUNTIME).then((c) => c.put(req, copy)).catch(() => undefined);
        }
        return res;
      }).catch(() => hit);
    })
  );
});
