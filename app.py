from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import jwt
import os
import json
import re
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# --- ASTRID Hybrid ML Backend ---
from chatbot_ml import AstridHybridML
print("\n" + "="*50)
print("ASTRID HYBRID ML: Initializing Knowledge Engine...")
print("Please wait while the brain is being prepared...")
print("="*50 + "\n")

dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
astrid_ai = AstridHybridML(dataset_dir)

print("\n" + "="*50)
print("ASTRID HYBRID ML: System Ready and Online!")
print("="*50 + "\n")
# --------------------------------

# ── ASTRID Chatbot (Scripted Navigation Layer) ─────────────────────────────────
# Note: LLM and Dataset layers removed for a lightweight, scripted experience.



app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'vetsync-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vetsync.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-jwt-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

db = SQLAlchemy(app)

# Configure Secure Session Cookies
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False, # Set to True if using HTTPS in production
    SESSION_COOKIE_SAMESITE='Lax',
)

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(80),  nullable=False)
    last_name     = db.Column(db.String(80),  nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    contact       = db.Column(db.String(30))
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default='client') # client, staff, admin
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    bookings      = db.relationship('Booking', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

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
    
    @property
    def no_show_risk(self):
        """Calculates risk based on client's past cancellations."""
        cancellations = Booking.query.filter_by(email=self.email, status='cancelled').count()
        return cancellations > 1
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

class Notification(db.Model):
    __tablename__ = 'notifications'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title         = db.Column(db.String(100), nullable=False)
    message       = db.Column(db.Text, nullable=False)
    read          = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    __tablename__ = 'reports'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(150), nullable=False)
    category      = db.Column(db.String(50), nullable=False)
    description   = db.Column(db.Text, nullable=False)
    status        = db.Column(db.String(20), default='Pending') # Pending, Reviewed, Resolved
    admin_comment = db.Column(db.Text, nullable=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)



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

def get_no_show_risk(email):
    """Predicts risk based on cancellation history."""
    if not email: return False
    cancellations = Booking.query.filter_by(email=email, status='cancelled').count()
    return cancellations > 1

# ===================== JWT UTILITIES =====================

def create_jwt_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')

def decode_jwt_token(token):
    try:
        return jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256']), 200
    except jwt.ExpiredSignatureError:
        return {'message': 'Token expired'}, 401
    except jwt.InvalidTokenError:
        return {'message': 'Invalid token'}, 401

def jwt_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        decoded_token, status_code = decode_jwt_token(token)
        if status_code != 200:
            return jsonify(decoded_token), status_code
        
        current_user_jwt = db.session.get(User, decoded_token['user_id'])
        if not current_user_jwt:
            return jsonify({'message': 'User not found'}), 401
        
        return f(current_user_jwt, *args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            if 'Authorization' in request.headers:
                parts = request.headers['Authorization'].split()
                if len(parts) == 2 and parts[0] == 'Bearer':
                    token = parts[1]
            if not token:
                return jsonify({'message': 'Token is missing!'}), 401
            
            decoded_token, status_code = decode_jwt_token(token)
            if status_code != 200:
                return jsonify(decoded_token), status_code
            
            current_user_jwt = db.session.get(User, decoded_token['user_id'])
            if not current_user_jwt:
                return jsonify({'message': 'User not found'}), 401
            
            if current_user_jwt.role not in roles:
                return jsonify({'message': 'Access denied: Insufficient role'}), 403
            
            return f(current_user_jwt, *args, **kwargs)
        return decorated_function
    return decorator


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


@app.route('/api/v1/chatbot/astrid', methods=['POST'])
def api_chat_hybrid():
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

    # 1. SCRIPTED MODE
    for key, answer in faq_answers.items():
        if key in message:
            return jsonify({'mode': 'scripted', 'reply': answer, 'type': 'faq'})

    # 2. SMART MODE
    smart_response = astrid_ai.get_smart_response(message)
    return jsonify(smart_response)


def booked_slots_on(q_date):
    taken = Booking.query.filter_by(date=q_date, status='confirmed').all()
    return {b.slot for b in taken}

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


@app.route('/offline')
def offline_page():
    return render_template('offline.html')


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
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('login.html')
            session['user_id'] = user.id
            flash('Logged in successfully.', 'success')
            
            # Role-based redirection for web interface
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'staff':
                return redirect(url_for('staff_dashboard'))
            else:
                next_url = request.args.get('next') or url_for('dashboard')
                return redirect(next_url)
        else:
            flash('Invalid email or password.', 'error')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/api/v1/login', methods=['POST'])
def api_v1_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        if not user.is_active:
            return jsonify({'message': 'Account deactivated'}), 401
        access_token = create_jwt_token(user.id, user.role)
        return jsonify(access_token=access_token, user_id=user.id, role=user.role), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401


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


# ── API v1 (PWA Endpoints) ───────────────────────────────────

from flask import Blueprint

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

@api_v1.route('/schedule', methods=['GET'])
@jwt_required
@role_required(['staff', 'admin'])
def get_schedule(current_user_jwt):
    blocks = DoctorAvailability.query.all()
    return jsonify([{'date': b.date.isoformat(), 'slot': b.slot, 'status': b.status} for b in blocks]), 200

@api_v1.route('/schedule/block', methods=['POST'])
@jwt_required
@role_required(['staff', 'admin'])
def block_time(current_user_jwt):
    data = request.get_json()
    try:
        d = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except:
        return jsonify({'error': 'Invalid date format'}), 400
        
    existing = DoctorAvailability.query.filter_by(date=d, slot=data['slot']).first()
    if not existing:
        db.session.add(DoctorAvailability(date=d, slot=data['slot'], status='unavailable'))
        db.session.commit()
    return jsonify({'message': 'Time slot blocked successfully'}), 201

@api_v1.route('/schedule/unblock', methods=['DELETE'])
@jwt_required
@role_required(['staff', 'admin'])
def unblock_time(current_user_jwt):
    data = request.get_json()
    try:
        d = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except:
        return jsonify({'error': 'Invalid date format'}), 400
        
    existing = DoctorAvailability.query.filter_by(date=d, slot=data['slot']).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    return jsonify({'message': 'Time slot is now available'}), 200

@api_v1.route('/users', methods=['GET', 'POST'])
@jwt_required
@role_required(['admin'])
def manage_users(current_user_jwt):
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            'id': u.id, 'first_name': u.first_name, 'last_name': u.last_name,
            'email': u.email, 'role': u.role, 'contact': u.contact, 'is_active': u.is_active
        } for u in users]), 200
    
    if request.method == 'POST':
        data = request.get_json()
        em = data['email'].strip().lower()
        
        if User.query.filter_by(email=em).first():
            return jsonify({'error': 'Email already exists'}), 409
            
        new_user = User(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=em,
            contact=data.get('contact', ''),
            role=data.get('role', 'client') # Default to client if not specified
        )
        new_user.set_password(data.get('password', 'default123')) # Default password for new users
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User created successfully', 'user_id': new_user.id}), 201

@api_v1.route('/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required
@role_required(['admin'])
def manage_single_user(current_user_jwt, user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': user.id, 'first_name': user.first_name, 'last_name': user.last_name,
            'email': user.email, 'role': user.role, 'contact': user.contact, 'is_active': user.is_active
        }), 200

    if request.method == 'PUT':
        data = request.get_json()
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email).strip().lower()
        user.contact = data.get('contact', user.contact)
        user.role = data.get('role', user.role)
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        db.session.commit()
        return jsonify({'message': 'User updated successfully'}), 200

    if request.method == 'DELETE':
        # For security, consider deactivating instead of hard deleting
        # For now, we'll hard delete as per common practice in simple APIs
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'}), 200


@api_v1.route('/appointments', methods=['GET', 'POST'])
@jwt_required
def api_appointments(current_user_jwt):
    if request.method == 'GET':
        if current_user_jwt.role in ['admin', 'staff']:
            bookings = Booking.query.all()
        else: # client
            bookings = Booking.query.filter_by(user_id=current_user_jwt.id).all()
            
        return jsonify([{
            'id': b.id,
            'service_id': b.service_id,
            'slot': b.slot,
            'date': b.date.isoformat(),
            'name': b.name,
            'email': b.email,
            'phone': b.phone,
            'pet_name': b.pet_name,
            'pet_type': b.pet_type,
            'status': b.status,
            'user_id': b.user_id,
            'no_show_risk': get_no_show_risk(b.email)
        } for b in bookings]), 200

    if request.method == 'POST':
        data = request.get_json()
        required_fields = ['service_id', 'slot', 'date', 'name', 'email', 'phone', 'pet_type']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            booking_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

        if booking_date < date.today():
            return jsonify({'error': 'Cannot book a date in the past'}), 400

        if data['slot'] in booked_slots_on(booking_date):
            return jsonify({'error': f"Sorry! {data['slot']} on {data['date']} was just booked. Please choose another slot."}), 409

        service = db.session.get(Service, data['service_id'])
        if not service:
            return jsonify({'error': 'Invalid service selected.'}), 400

        booking = Booking(
            service_id      = data['service_id'],
            slot            = data['slot'],
            date            = booking_date,
            name            = data['name'],
            email           = data['email'],
            phone           = data['phone'],
            alt_phone       = data.get('alt_phone'),
            address         = data.get('address'),
            pet_name        = data.get('pet_name'),
            pet_type        = data['pet_type'],
            pet_breed       = data.get('pet_breed'),
            pet_sex         = data.get('pet_sex'),
            pet_age         = data.get('pet_age'),
            pet_weight      = data.get('pet_weight'),
            pet_color       = data.get('pet_color'),
            visit_reason    = data.get('visit_reason'),
            medical_history = data.get('medical_history'),
            allergies       = data.get('allergies'),
            notes           = data.get('notes'),
            payment_method  = data.get('payment_method'),
            consent         = data.get('consent', False),
            status          = 'confirmed',
            user_id         = current_user_jwt.id,
        )
        db.session.add(booking)
        db.session.commit()
        return jsonify({'message': 'Booking created successfully', 'booking_id': booking.id}), 201

@api_v1.route('/appointments/<int:booking_id>', methods=['PUT'])
@jwt_required
@role_required(['staff', 'admin'])
def update_appointment(current_user_jwt, booking_id):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
        
    data = request.get_json()
    if 'status' in data:
        if data['status'] not in ['confirmed', 'pending', 'cancelled', 'completed']:
            return jsonify({'error': 'Invalid status'}), 400
        booking.status = data['status']
        
    db.session.commit()
    return jsonify({'message': 'Booking updated successfully', 'status': booking.status}), 200


@api_v1.route('/notifications', methods=['GET', 'POST'])
@jwt_required
def api_notifications(current_user_jwt):
    if request.method == 'GET':
        notifications = Notification.query.filter_by(user_id=current_user_jwt.id).order_by(Notification.created_at.desc()).all()
        return jsonify([{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'read': n.read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]), 200
    
    if request.method == 'POST':
        data = request.get_json()
        title = data.get('title')
        message = data.get('message')
        target_user_id = data.get('user_id') # Optional: for admin to send to specific user

        if not title or not message:
            return jsonify({'error': 'Title and message are required'}), 400

        if target_user_id and current_user_jwt.role == 'admin':
            user_to_notify = db.session.get(User, target_user_id)
            if not user_to_notify:
                return jsonify({'error': 'Target user not found'}), 404
            new_notification = Notification(user_id=target_user_id, title=title, message=message)
        else:
            new_notification = Notification(user_id=current_user_jwt.id, title=title, message=message)
        
        db.session.add(new_notification)
        db.session.commit()
        return jsonify({'message': 'Notification sent successfully', 'notification_id': new_notification.id}), 201

@api_v1.route('/workload', methods=['GET'])
@jwt_required
@role_required(['staff', 'admin'])
def get_workload_api(current_user_jwt):
    today = date.today()
    counts = {}
    for slot in ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM",
                "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM",
                "6:00 PM", "7:00 PM", "8:00 PM", "9:00 PM"]:
        count = Booking.query.filter_by(date=today, slot=slot, status='confirmed').count()
        counts[slot] = count
    
    total_slots = 14 # Total working slots
    confirmed_today = Booking.query.filter_by(date=today, status='confirmed').count()
    percentage = (confirmed_today / total_slots * 100) if total_slots > 0 else 0
    
    return jsonify({
        'hourly': counts,
        'total_confirmed': confirmed_today,
        'percentage': round(percentage, 1)
    }), 200


@api_v1.route('/reports', methods=['GET', 'POST'])
@jwt_required
@role_required(['staff', 'admin'])
def api_reports(current_user_jwt):
    if request.method == 'GET':
        if current_user_jwt.role == 'admin':
            reports = Report.query.order_by(Report.created_at.desc()).all()
        else:
            reports = Report.query.filter_by(user_id=current_user_jwt.id).order_by(Report.created_at.desc()).all()
            
        return jsonify([{
            'id': r.id,
            'title': r.title,
            'category': r.category,
            'description': r.description,
            'status': r.status,
            'admin_comment': r.admin_comment,
            'user_id': r.user_id,
            'staff_name': db.session.get(User, r.user_id).first_name + " " + db.session.get(User, r.user_id).last_name if db.session.get(User, r.user_id) else "Unknown",
            'created_at': r.created_at.strftime('%b %d, %Y')
        } for r in reports]), 200

    if request.method == 'POST':
        data = request.get_json()
        if not data.get('title') or not data.get('description'):
            return jsonify({'error': 'Title and description are required'}), 400
            
        report = Report(
            title=data.get('title'),
            category=data.get('category', 'Other'),
            description=data.get('description'),
            user_id=current_user_jwt.id
        )
        db.session.add(report)
        db.session.commit()
        return jsonify({'message': 'Report submitted successfully'}), 201

@api_v1.route('/reports/<int:report_id>', methods=['PUT', 'DELETE'])
@jwt_required
@role_required(['admin'])
def api_report_detail(current_user_jwt, report_id):
    report = db.session.get(Report, report_id)
    if not report:
        return jsonify({'error': 'Report not found'}), 404
        
    if request.method == 'PUT':
        data = request.get_json()
        if 'status' in data:
            report.status = data['status']
        if 'admin_comment' in data:
            report.admin_comment = data['admin_comment']
        db.session.commit()
        return jsonify({'message': 'Report updated successfully'})
        
    if request.method == 'DELETE':
        db.session.delete(report)
        db.session.commit()
        return jsonify({'message': 'Report deleted successfully'})


app.register_blueprint(api_v1)

# ===================== INIT =====================

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True)