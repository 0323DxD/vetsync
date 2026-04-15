const CACHE_NAME = 'vetcare-v3';
const STATIC_ASSETS = [
  '/',
  '/offline',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/manifest.json',
  '/static/images/vet-dog.png',
  'https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Poppins:wght@300;400;500;600;700&display=swap'
];

// Install: Cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('SW: Pre-caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: Cleanup old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch Strategy: Network First for API/Pages, Stale-While-Revalidate for Statics
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET requests or requests from other origins (except fonts)
  if (event.request.method !== 'GET' || (!url.origin.includes(location.hostname) && !url.origin.includes('fonts'))) {
    return;
  }

  // Handle API and dynamic pages (Network First)
  if (url.pathname.startsWith('/api/') || !url.pathname.includes('/static/')) {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          // Clone response and cache it
          const clonedResponse = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clonedResponse));
          return networkResponse;
        })
        .catch(() => {
          return caches.match(event.request).then(cachedResponse => {
            return cachedResponse || caches.match('/offline');
          });
        })
    );
  } else {
    // Handle static assets (Stale-While-Revalidate)
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        const fetchPromise = fetch(event.request).then(networkResponse => {
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, networkResponse.clone()));
          return networkResponse;
        });
        return cachedResponse || fetchPromise;
      })
    );
  }
});
