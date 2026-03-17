const CACHE_NAME = 'rmc-bot-v1';
const ASSETS = [
    '/',
    '/static/style.css',
    '/static/script.js',
    '/static/favicon.png'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    // Always go to network for API calls (live data)
    if (url.pathname.startsWith('/api/')) {
        return event.respondWith(fetch(event.request));
    }
    // For static assets, try cache first then network
    event.respondWith(
        caches.match(event.request).then(cached => cached || fetch(event.request))
    );
});
