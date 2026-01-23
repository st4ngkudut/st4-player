// Minimal Service Worker untuk PWA
self.addEventListener('install', (e) => {
  console.log('[Service Worker] Install');
});

self.addEventListener('fetch', (e) => {
  // Pass-through (tidak caching agresif, biar development enak)
  e.respondWith(fetch(e.request));
});