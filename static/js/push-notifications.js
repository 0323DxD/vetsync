/**
 * Client-Side Push Notification Manager
 * Handles permissions, subscription, and server sync.
 */

const PUSH_VAPID_URL = '/api/v1/push/public-key';
const PUSH_SUB_URL = '/api/v1/push/subscribe';

// Utility: Normalize VAPID Public Key for the browser
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function initPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.warn('Push notifications not supported by this browser.');
        return;
    }

    try {
        const registration = await navigator.serviceWorker.ready;
        let subscription = await registration.pushManager.getSubscription();

        if (!subscription) {
            // Fetch VAPID Key
            const res = await fetch(PUSH_VAPID_URL);
            const { public_key } = await res.json();
            const convertedKey = urlBase64ToUint8Array(public_key);

            // Request Permission & Subscribe
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: convertedKey
            });
            
            console.log('User subscribed to push.');
        }

        // Send subscription to server
        await syncSubscriptionWithServer(subscription);
    } catch (err) {
        console.error('Push subscription failed:', err);
    }
}

async function syncSubscriptionWithServer(subscription) {
    // Get JWT from localStorage or similar where you store your API token
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
        const key = subscription.getKey('p256dh');
        const auth = subscription.getKey('auth');

        await fetch(PUSH_SUB_URL, {
            method: 'POST',
            body: JSON.stringify({
                endpoint: subscription.endpoint,
                keys: {
                    p256dh: btoa(String.fromCharCode.apply(null, new Uint8Array(key))),
                    auth: btoa(String.fromCharCode.apply(null, new Uint8Array(auth)))
                }
            }),
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });
        console.log('Subscription synced with server.');
    } catch (err) {
        console.error('Failed to sync subscription:', err);
    }
}

// Auto-init for logged-in users on dashboard or relevant pages
window.addEventListener('load', () => {
    // Check if on dashboard or if user is logged in
    if (window.location.pathname.includes('/dashboard')) {
        // Small delay to ensure everything is ready
        setTimeout(initPushNotifications, 2000);
    }
});
