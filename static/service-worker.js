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
  // ... existing fetch logic
});

// Push: Handle incoming notifications
self.addEventListener('push', event => {
  console.log('SW: Push received');
  let data = { title: 'VetSync Update', body: 'You have a new update from VetSync.', icon: '/static/images/vet-dog.png' };
  
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) {
    console.error('Push data parse error:', e);
  }

  const options = {
    body: data.body,
    icon: data.icon || '/static/images/vet-dog.png',
    badge: '/static/images/vet-dog.png',
    data: data.data || { url: '/dashboard' },
    vibrate: [100, 50, 100],
    actions: [
      { action: 'view', title: 'View Update' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification Click: Navigate to URL
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const urlToOpen = event.notification.data.url || '/dashboard';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (let i = 0; i < windowClients.length; i++) {
        const client = windowClients[i];
        if (client.url === urlToOpen && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
