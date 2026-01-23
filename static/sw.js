const CACHE_NAME = 'st4-player-v1';
const ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/css/all.min.css',
    '/static/js/script.js',
    '/static/img/default.png',
    '/static/manifest.json'
];

// Install Event - Cache file penting
self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS);
        })
    );
});

// Activate Event - Hapus cache lama kalau ada update
self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
});

// Fetch Event - Serve dari cache dulu, baru network (Stale-while-revalidate)
self.addEventListener('fetch', (e) => {
    // Jangan cache request API /control/ atau /status biar gak nge-bug
    if (e.request.url.includes('/control/') || 
        e.request.url.includes('/status') || 
        e.request.url.includes('/queue/') ||
        e.request.method !== 'GET') {
        return;
    }

    e.respondWith(
        caches.match(e.request).then((cachedResp) => {
            return cachedResp || fetch(e.request).then((fetchResp) => {
                // Opsional: Cache dynamic images (covers)
                if (e.request.url.includes('/static/covers/')) {
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(e.request, fetchResp.clone());
                        return fetchResp;
                    });
                }
                return fetchResp;
            });
        })
    );
});