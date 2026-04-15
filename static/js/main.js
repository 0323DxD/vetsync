// ===================== NAVBAR =====================
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
});

function toggleMenu() {
    document.querySelector('.nav-links').classList.toggle('open');
}
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', () => {
        document.querySelector('.nav-links').classList.remove('open');
    });
});

// ===================== SMOOTH SCROLL =====================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - 80, behavior: 'smooth' });
        }
    });
});

// ===================== SCROLL ANIMATIONS =====================
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, { threshold: 0.1 });

document.querySelectorAll('.service-card, .stat-card, .team-card, .service-full-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
});

// ===================== FLASH AUTO-DISMISS =====================
setTimeout(() => {
    document.querySelectorAll('.flash').forEach(el => {
        el.style.transition = 'opacity 0.5s';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 500);
    });
}, 4000);

// ===================== OFFLINE SYNC (IndexedDB) =====================
const DB_NAME = 'VetCareOfflineDB';
const DB_VERSION = 1;
const STORE_NAME = 'offline_bookings';

function openDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
        request.onsuccess = (e) => resolve(e.target.result);
        request.onerror = (e) => reject(e.target.error);
    });
}

async function saveOfflineBooking(bookingData) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.add(bookingData);
        request.onsuccess = () => resolve(true);
        request.onerror = () => reject(false);
    });
}

async function getOfflineBookings() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function clearOfflineBookings() {
    const db = await openDB();
    const transaction = db.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    store.clear();
}

async function syncOfflineBookings() {
    if (!navigator.onLine) return;
    
    const offlineBookings = await getOfflineBookings();
    if (offlineBookings.length === 0) return;

    console.log(`Syncing ${offlineBookings.length} offline bookings...`);
    
    for (const booking of offlineBookings) {
        try {
            const formData = new FormData();
            for (const key in booking) {
                if (key !== 'id') formData.append(key, booking[key]);
            }

            const response = await fetch('/book', {
                method: 'POST',
                body: formData
            });

            if (response.ok || response.status === 400) {
                // Remove synced or invalid bookings
                const db = await openDB();
                const transaction = db.transaction(STORE_NAME, 'readwrite');
                transaction.objectStore(STORE_NAME).delete(booking.id);
            }
        } catch (err) {
            console.error('Sync failed for booking:', booking, err);
        }
    }
}

// Sync when coming back online
window.addEventListener('online', syncOfflineBookings);

// Handle booking form submission with offline support
const bookingForm = document.querySelector('form[action="/book"]');
if (bookingForm) {
    bookingForm.addEventListener('submit', async (e) => {
        if (!navigator.onLine) {
            e.preventDefault();
            const formData = new FormData(bookingForm);
            const bookingData = {};
            formData.forEach((value, key) => { bookingData[key] = value; });
            
            try {
                await saveOfflineBooking(bookingData);
                alert('You are offline. Your booking has been saved locally and will be synced once you are back online.');
                window.location.href = '/dashboard'; // Redirect to dashboard or a success page
            } catch (err) {
                alert('Failed to save booking offline.');
            }
        }
    });
}

// Initial sync attempt
if (navigator.onLine) {
    syncOfflineBookings();
}

// ===================== DATE PICKER – set min to today =====================
const dateInput = document.getElementById('booking-date');
const slotSelect = document.getElementById('slot-select');
const slotLoading = document.getElementById('slot-loading');

if (dateInput) {
    // Prevent past dates
    const today = new Date().toISOString().split('T')[0];
    dateInput.setAttribute('min', today);

    dateInput.addEventListener('change', async () => {
        const selectedDate = dateInput.value;
        if (!selectedDate) return;

        // Show loading state
        slotSelect.disabled = true;
        slotSelect.innerHTML = '<option value="">Loading...</option>';
        if (slotLoading) slotLoading.style.display = 'block';

        try {
            const res = await fetch(`/api/available-slots?date=${selectedDate}`);
            const data = await res.json();

            slotSelect.innerHTML = '<option value="">Select a time slot ▾</option>';

            let hasAvailable = false;
            data.slots.forEach(slot => {
                const opt = document.createElement('option');
                opt.value = slot.time;

                if (slot.available) {
                    opt.textContent = `🕐 ${slot.time}`;
                    hasAvailable = true;
                } else {
                    opt.textContent = `❌ ${slot.time} — Booked`;
                    opt.disabled = true;
                    opt.classList.add('booked');
                }
                slotSelect.appendChild(opt);
            });

            slotSelect.disabled = false;

            if (!hasAvailable) {
                slotSelect.innerHTML = '<option value="">No slots available on this date</option>';
                slotSelect.disabled = true;
            }
        } catch (err) {
            slotSelect.innerHTML = '<option value="">Error loading slots</option>';
            console.error('Slot fetch error:', err);
        } finally {
            if (slotLoading) slotLoading.style.display = 'none';
        }
    });
}
