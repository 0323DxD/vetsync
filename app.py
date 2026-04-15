from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
import json
import re
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# ── ASTRID Chatbot (Scripted Navigation Layer) ─────────────────────────────────
# Note: LLM and Dataset layers removed for a lightweight, scripted experience.



app = Flask(__name__)
app.secret_key = 'vetsync-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vetsync.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ===================== MODELS =====================

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(80),  nullable=False)
    last_name     = db.Column(db.String(80),  nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    contact       = db.Column(db.String(30))
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default='client') # client, staff, admin
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    bookings      = db.relationship('Booking', backref='user', lazy=True)

    def set_password(self, p):   self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)


class Service(db.Model):
    __tablename__ = 'services'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    icon     = db.Column(db.String(10))
    desc     = db.Column(db.Text)
    bookings = db.relationship('Booking', backref='service_ref', lazy=True)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id             = db.Column(db.Integer, primary_key=True)
    # Appointment
    service_id     = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    slot           = db.Column(db.String(20),  nullable=False)
    date           = db.Column(db.Date,        nullable=False)
    # Owner info
    name           = db.Column(db.String(120), nullable=False)
    email          = db.Column(db.String(120), nullable=False)
    phone          = db.Column(db.String(30),  nullable=False)
    alt_phone      = db.Column(db.String(30))
    address        = db.Column(db.String(255))
    # Pet info
    pet_name       = db.Column(db.String(80))
    pet_type       = db.Column(db.String(50),  nullable=False)
    pet_breed      = db.Column(db.String(100))
    pet_sex        = db.Column(db.String(30))
    pet_age        = db.Column(db.String(30))
    pet_weight     = db.Column(db.String(20))
    pet_color      = db.Column(db.String(100))
    # Medical
    visit_reason   = db.Column(db.Text)
    medical_history= db.Column(db.Text)
    allergies      = db.Column(db.String(255))
    notes          = db.Column(db.Text)
    # Payment & consent
    payment_method = db.Column(db.String(50))
    consent        = db.Column(db.Boolean, default=False)
    # Meta
    status         = db.Column(db.String(20), default='confirmed')
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availability'
    id         = db.Column(db.Integer, primary_key=True)
    date       = db.Column(db.Date, nullable=False)
    slot       = db.Column(db.String(20), nullable=False)
    status     = db.Column(db.String(20), default='unavailable') 

class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), nullable=False)
    subject    = db.Column(db.String(200))
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===================== CONSTANTS =====================

ALL_SLOTS = ["9:00 AM","10:00 AM","11:00 AM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"]
PET_TYPES = ["Dog","Cat","Bird","Rabbit","Reptile","Other"]


# ===================== SEED =====================

def seed_data():
    if Service.query.count() == 0:
        db.session.add_all([
            Service(name="General Checkup", icon="🩺", desc="Comprehensive health examination for your pet"),
            Service(name="Vaccination",     icon="💉", desc="Keep your pet protected with up-to-date vaccines"),
            Service(name="Dental Care",     icon="🦷", desc="Professional dental cleaning and oral health care"),
            Service(name="Surgery",         icon="🏥", desc="Advanced surgical procedures with expert veterinarians"),
            Service(name="Grooming",        icon="✂️",  desc="Full grooming services to keep your pet looking great"),
            Service(name="Emergency Care",  icon="🚨", desc="24/7 emergency veterinary care for urgent situations"),
        ])
    if not User.query.filter_by(email='demo@vetsync.com').first():
        u = User(first_name='Demo', last_name='User',
                 email='demo@vetsync.com', contact='0000000000', role='client')
        u.set_password('demo123')
        db.session.add(u)
    if not User.query.filter_by(email='adminvetclinic@gmail.com').first():
        u = User(first_name='Admin', last_name='VetSync',
                 email='adminvetclinic@gmail.com', contact='0000000001', role='admin')
        u.set_password('vetadminclinic1214')
        db.session.add(u)
    if not User.query.filter_by(email='veterinarian123@gmail.com').first():
        u = User(first_name='Staff', last_name='Veterinarian',
                 email='veterinarian123@gmail.com', contact='0000000002', role='staff')
        u.set_password('vet121516')
        db.session.add(u)
    db.session.commit()


# ===================== HELPERS =====================

def current_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None

@app.context_processor
def inject_user():
    return dict(current_user=current_user())

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            flash('Please log in to access that page.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user or user.role != 'admin':
            flash('Access denied: Admins only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def staff_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user or user.role not in ['admin', 'staff']:
            flash('Access denied: Staff only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def booked_slots_on(q_date):
    taken = Booking.query.filter_by(date=q_date, status='confirmed').all()
    return {b.slot for b in taken}


# ===================== ROUTES =====================

@app.route('/')
def index():
    services = Service.query.all()
    today    = date.today().isoformat()
    return render_template('index.html', services=services,
                           pet_types=PET_TYPES, today=today)


# ── Booking page (auth-guarded) ──────────────────────────────

@app.route('/booking')
@login_required
def booking_page():
    user     = current_user()
    services = Service.query.all()
    today    = date.today().isoformat()
    return render_template('booking_page.html', user=user,
                           services=services, pet_types=PET_TYPES, today=today)


@app.route('/book', methods=['POST'])
@login_required
def book():
    g    = lambda k: request.form.get(k, '').strip()
    name       = g('name')
    email      = g('email')
    phone      = g('phone')
    pet_type   = g('pet_type')
    service_id = g('service')
    slot       = g('slot')
    date_str   = g('date')

    if not all([name, email, phone, pet_type, service_id, slot, date_str]):
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('booking_page'))

    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date selected.', 'error')
        return redirect(url_for('booking_page'))

    if booking_date < date.today():
        flash('Cannot book a date in the past.', 'error')
        return redirect(url_for('booking_page'))

    if slot in booked_slots_on(booking_date):
        flash(f'Sorry! {slot} on {booking_date.strftime("%b %d")} was just booked. Please choose another slot.', 'error')
        return redirect(url_for('booking_page'))

    service = db.session.get(Service, service_id)
    if not service:
        flash('Invalid service selected.', 'error')
        return redirect(url_for('booking_page'))

    user    = current_user()
    consent = request.form.get('consent') == 'on'

    booking = Booking(
        service_id      = service.id,
        slot            = slot,
        date            = booking_date,
        name            = name,
        email           = email,
        phone           = phone,
        alt_phone       = g('alt_phone'),
        address         = g('address'),
        pet_name        = g('pet_name'),
        pet_type        = pet_type,
        pet_breed       = g('pet_breed'),
        pet_sex         = g('pet_sex'),
        pet_age         = g('pet_age'),
        pet_weight      = g('pet_weight'),
        pet_color       = g('pet_color'),
        visit_reason    = g('visit_reason'),
        medical_history = g('medical_history'),
        allergies       = g('allergies'),
        notes           = g('notes'),
        payment_method  = g('payment_method'),
        consent         = consent,
        status          = 'confirmed',
        user_id         = user.id,
    )
    db.session.add(booking)
    db.session.commit()

    flash(f'🎉 Booking confirmed! {service.name} for {g("pet_name") or "your pet"} on {booking_date.strftime("%B %d, %Y")} at {slot}.', 'success')
    return redirect(url_for('dashboard'))


# ── API ──────────────────────────────────────────────────────

# Knowledge Base loading removed for scripted version.
def _load_kb():
    return {'keyword_map': {}, 'knowledge_base': {}, 'vet_med_qa': [], 'vetcare_pro': []}



def _build_health_reply(entry, species_filter=None):
    """
    Format a knowledge base entry into a friendly chatbot reply.
    Returns a dict with 'text' and 'show_booking' flag.
    """
    lines = []
    label   = entry.get('label', 'This condition')
    emoji   = entry.get('emoji', 'vet')
    species = entry.get('species', [])

    # Species-specific header note
    species_note = ""
    if species_filter and species and species_filter not in species and 'general' not in species:
        species_note = f"Note: This info may not fully apply to {species_filter}s."

    lines.append(f"{emoji} {label}")
    if species_note:
        lines.append(f"({species_note})")
    lines.append("")

    causes = entry.get('possible_causes', [])
    if causes:
        lines.append("Possible causes:")
        for c in causes[:4]:
            lines.append(f"  - {c}")
        lines.append("")

    first_aid = entry.get('first_aid', [])
    if first_aid:
        lines.append("What you can do at home:")
        for tip in first_aid[:4]:
            lines.append(f"  - {tip}")
        lines.append("")

    see_vet = entry.get('see_vet_if', [])
    if see_vet:
        lines.append("See a vet immediately if:")
        for sv in see_vet[:3]:
            lines.append(f"  ! {sv}")
        lines.append("")

    lines.append("-----")
    lines.append("This is general guidance only and NOT a substitute for professional veterinary diagnosis.")
    lines.append("Book an appointment with our vet for proper evaluation.")

    return {
        'text':         "\n".join(lines),
        'show_booking': True,
        'condition':    label,
        'emoji':        emoji,
    }


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data    = request.get_json() or {}
    message = data.get('message', '').lower().strip()

    faq_answers = {
        "how to book":      "<strong>To book an appointment:</strong><ol><li>Log in to your account.</li><li>Go to your Dashboard.</li><li>Click 'Book Appointment'.</li><li>Select your pet, service, date, and time slot.</li></ol><em>Disclaimer: For urgent emergency cases, please call the clinic directly instead of booking online.</em>",
        "book appointment": "<strong>To book an appointment:</strong><ol><li>Log in to your account.</li><li>Go to your Dashboard.</li><li>Click 'Book Appointment'.</li><li>Select your pet, service, date, and time slot.</li></ol><em>Disclaimer: For urgent emergency cases, please call the clinic directly instead of booking online.</em>",
        "clinic hours":     "<strong>VetSync Clinic Hours:</strong><br><br>Monday - Saturday: 8:00 AM - 6:00 PM<br>Sunday & Holidays: CLOSED<br><br><em>For emergencies outside clinic hours, call our 24/7 hotline: (02) 8123-4567</em>",
        "what are the offers": "We frequently have seasonal offers! Right now, we offer a <strong>10% discount on first-time checkups</strong> and discounted vaccination bundles.<br><br>Book an appointment online to secure these offers.",
        "how to view my pets": "<strong>To view your pets:</strong><ol><li>Log in to your account.</li><li>Navigate to your Dashboard.</li><li>Look for the 'My Pets' section to view all registered pet profiles.</li></ol>",
        "how to check services": "Our primary services include:<br><ul><li>General Checkup</li><li>Vaccination</li><li>Dental Care</li><li>Surgery</li><li>Grooming</li><li>Emergency Care</li></ul><br>Click 'Services' on the top navigation bar to see detailed pricing.",
        "how to leave a review": "<strong>To leave a review:</strong><ol><li>Log in to your account.</li><li>Go to your Dashboard.</li><li>Locate a completed appointment.</li><li>Click 'Leave a Review' to share your experience!</li></ol>",
        "how to sign up":   "<strong>To sign up:</strong><ol><li>Click 'Sign Up' at the top right.</li><li>Fill in your name, email, contact, and password.</li><li>Log in and start booking for your pet!</li></ol>",
        "how to log in":    "<strong>To log in:</strong><br>Click 'Log In' on the top right and enter your registered email and password."
    }

    for key, answer in faq_answers.items():
        if key in message:
            return jsonify({'reply': answer, 'type': 'faq'})

    # Default fallback for unmatched queries
    fallback = (
        "I'm ASTRID, your VetSync clinic assistant!\n\n"
        "Please select one of the options from the menu to get started, "
        "or contact our clinic directly for specific medical advice."
    )
    return jsonify({'reply': fallback, 'type': 'fallback', 'show_booking': False})



# ─── /api/chat/health — Species-filtered pet health endpoint ─────────────────
@app.route('/api/chat/health', methods=['POST'])
def api_chat_health():
    """
    Dedicated pet health endpoint with species filtering.
    POST body: { "message": "...", "species": "dog" | "cat" | "rabbit" | "bird" | "" }
    Returns structured health advice + booking flag.
    """
    data           = request.get_json() or {}
    message        = data.get('message', '').lower().strip()
    species_filter = data.get('species', '').lower().strip()  # e.g. 'dog', 'cat', 'rabbit', 'bird'

    valid_species = {'dog', 'cat', 'rabbit', 'bird', 'reptile', 'other'}

    kb      = _load_kb()
    kw_map  = kb.get('keyword_map', {})
    kb_data = kb.get('knowledge_base', {})

    # Find matched symptom key
    matched_key = None
    for keyword, kb_key in kw_map.items():
        if keyword in message:
            matched_key = kb_key
            break

    if not matched_key:
        for kb_key in kb_data:
            if kb_key.replace('_', ' ') in message:
                matched_key = kb_key
                break

    if not matched_key:
        # Try vet_med Q&A keyword search
        vet_med_qa = kb.get('vet_med_qa', [])
        for pair in vet_med_qa[:200]:
            q   = pair.get('question', '').lower()
            any_kw = any(kw in q for kw in message.split() if len(kw) > 3)
            if any_kw and message in q:
                return jsonify({
                    'reply':        pair['answer'],
                    'type':         'vet_med',
                    'show_booking': True,
                    'source':       'vet_med_dataset',
                    'condition':    'Veterinary Q&A',
                    'emoji':        'vet',
                })

    if matched_key and matched_key in kb_data:
        entry   = kb_data[matched_key]
        species = entry.get('species', [])

        # Species filter: warn if entry doesn't cover this animal
        species_match = (
            not species_filter
            or species_filter not in valid_species
            or species_filter in species
            or 'general' in species
        )

        result = _build_health_reply(entry, species_filter if species_filter else None)

        return jsonify({
            'reply':         result['text'],
            'type':          'health',
            'show_booking':  True,
            'condition':     result['condition'],
            'emoji':         result['emoji'],
            'species_match': species_match,
            'species_filter': species_filter or 'any',
            'matched_key':   matched_key,
        })

    # No match
    return jsonify({
        'reply':        (
            f"I couldn't find specific information for that symptom"
            f"{' in ' + species_filter + 's' if species_filter else ''}. "
            "Try describing the symptom differently or book an appointment for a proper diagnosis."
        ),
        'type':         'no_match',
        'show_booking': True,
        'species_filter': species_filter or 'any',
    })


@app.route('/api/available-slots')
def available_slots():
    date_str = request.args.get('date', '')
    try:
        q_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date'}), 400
    if q_date < date.today():
        return jsonify({'date': date_str, 'slots': [{'time': s, 'available': False} for s in ALL_SLOTS]})
    taken = booked_slots_on(q_date)
    return jsonify({'date': date_str,
                    'slots': [{'time': s, 'available': s not in taken} for s in ALL_SLOTS]})

@app.route('/api/services')
def get_services():
    return jsonify([{'id': s.id, 'name': s.name, 'icon': s.icon}
                    for s in Service.query.all()])


# ── Auth ─────────────────────────────────────────────────────

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        fn  = request.form.get('first_name','').strip()
        ln  = request.form.get('last_name','').strip()
        em  = request.form.get('email','').strip().lower()
        ct  = request.form.get('contact','').strip()
        pw  = request.form.get('password','')
        pw2 = request.form.get('re_password','')
        if pw != pw2:
            flash('Passwords do not match.', 'error'); return render_template('signup.html')
        if len(pw) < 6:
            flash('Password must be at least 6 characters.', 'error'); return render_template('signup.html')
        if User.query.filter_by(email=em).first():
            flash('Email already registered.', 'error'); return render_template('signup.html')
        u = User(first_name=fn, last_name=ln, email=em, contact=ct)
        u.set_password(pw)
        db.session.add(u); db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        em = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        u  = User.query.filter_by(email=em).first()
        if u and u.check_password(pw):
            session['user_id'] = u.id
            session['user']    = u.first_name
            flash(f'Welcome back, {u.first_name}!', 'success')
            
            # Role-based redirection
            if u.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif u.role == 'staff':
                return redirect(url_for('staff_dashboard'))
            else:
                next_url = request.args.get('next') or url_for('dashboard')
                return redirect(next_url)
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))


# ── Other pages ──────────────────────────────────────────────

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/services')
def services_page(): return render_template('services.html', services=Service.query.all())

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        n = request.form.get('name','').strip()
        e = request.form.get('email','').strip()
        s = request.form.get('subject','').strip()
        m = request.form.get('message','').strip()
        if not all([n, e, m]):
            flash('Please fill in all required fields.', 'error')
            return render_template('contact.html')
        db.session.add(ContactMessage(name=n, email=e, subject=s, message=m))
        db.session.commit()
        flash('Message sent! We will get back to you shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user     = current_user()
    if user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user.role == 'staff':
        return redirect(url_for('staff_dashboard'))

    bookings = (Booking.query.filter_by(user_id=user.id)
                .order_by(Booking.created_at.desc()).all())
    return render_template('dashboard.html', user=user, bookings=bookings)

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    user = current_user()
    
    # Calculate Metrics
    from sqlalchemy import func
    total_users = User.query.count()
    total_pets  = db.session.query(func.count(func.distinct(Booking.pet_name))).scalar() or 0
    today_appointments = Booking.query.filter_by(date=date.today()).count()
    
    # Simple month calculation
    current_month = date.today().month
    current_year  = date.today().year
    
    # In SQLite, extracting month from date is tricky, but we can filter via python
    # For a real DB, extract(month) would be used.
    # Simple approach: fetch all and filter, or use basic comparison if dates are strings.
    # SQLAlchemy queries natively using standard date if mapped.
    total_bookings_this_month = 0
    all_books = Booking.query.all()
    for b in all_books:
        if b.date.month == current_month and b.date.year == current_year:
            total_bookings_this_month += 1

    staff_members = User.query.filter(User.role.in_(['staff', 'admin'])).all()

    return render_template('admin_dashboard.html', 
                           user=user, 
                           total_users=total_users,
                           total_pets=total_pets,
                           today_appointments=today_appointments,
                           total_bookings_this_month=total_bookings_this_month,
                           staff_members=staff_members)

@app.route('/staff/dashboard')
@login_required
@staff_required
def staff_dashboard():
    user = current_user()
    from sqlalchemy import func
    
    today = date.today()
    today_appointments = Booking.query.filter_by(date=today).count()
    upcoming_appointments = Booking.query.filter(Booking.date > today, Booking.status == 'confirmed').count()
    pending_bookings = Booking.query.filter_by(status='pending').count()
    
    # Total patients this month
    total_patients_this_month = 0
    all_books = Booking.query.all()
    for b in all_books:
        if b.date.month == today.month and b.date.year == today.year:
            total_patients_this_month += 1

    bookings = Booking.query.order_by(Booking.date.asc(), Booking.slot.asc()).all()
    
    # Prepare JSON data for Calendar
    b_json = []
    for b in bookings:
        b_json.append({
            'id': b.id,
            'date': b.date.isoformat(),
            'slot': b.slot,
            'client_name': b.name,
            'pet_name': b.pet_name,
            'pet_type': b.pet_type,
            'service': b.service_ref.name,
            'status': b.status
        })

    return render_template('staff_dashboard.html', 
                           user=user, 
                           today_appointments=today_appointments,
                           upcoming_appointments=upcoming_appointments,
                           pending_bookings=pending_bookings,
                           total_patients_this_month=total_patients_this_month,
                           bookings=bookings,
                           bookings_json=json.dumps(b_json))

@app.route('/api/availability', methods=['GET', 'POST'])
@login_required
@staff_required
def api_availability():
    if request.method == 'GET':
        blocks = DoctorAvailability.query.all()
        return jsonify([{'date': b.date.isoformat(), 'slot': b.slot, 'status': b.status} for b in blocks])
    
    if request.method == 'POST':
        data = request.get_json()
        target_date = data.get('date')
        slot = data.get('slot')
        
        if not target_date or not slot:
            return jsonify({'error': 'Missing data'}), 400
            
        try:
            d = datetime.strptime(target_date, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'error': 'Invalid date format'}), 400
            
        existing = DoctorAvailability.query.filter_by(date=d, slot=slot).first()
        if existing:
            db.session.delete(existing) # Toggle it off (make it available)
            status = 'available'
        else:
            new_block = DoctorAvailability(date=d, slot=slot, status='unavailable')
            db.session.add(new_block)
            status = 'unavailable'
            
        db.session.commit()
        return jsonify({'success': True, 'date': target_date, 'slot': slot, 'new_status': status})


@app.route('/booking/cancel/<int:bid>', methods=['POST'])
@login_required
def cancel_booking(bid):
    user    = current_user()
    booking = db.session.get(Booking, bid)
    if not booking or booking.user_id != user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    booking.status = 'cancelled'
    db.session.commit()
    flash('Booking cancelled successfully.', 'success')
    return redirect(url_for('dashboard'))


# ===================== INIT =====================

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True)
