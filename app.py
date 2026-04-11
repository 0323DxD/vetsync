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

# ── Gemini Flash LLM (Layer 3) ──────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
_gemini_client = None

ASTRID_SYSTEM_PROMPT = """You are ASTRID, a friendly and caring AI veterinary assistant for VetSync Clinic.

RULES:
- Be empathetic, warm, and professional in every response.
- NEVER give a definitive diagnosis. Only suggest POSSIBLE causes and general advice.
- ALWAYS include this disclaimer at the end: "This is general guidance only and NOT a substitute for professional veterinary diagnosis. Please book an appointment with our vet for proper evaluation."
- If the situation sounds urgent (bleeding, seizure, collapse, difficulty breathing, poisoning), STRONGLY urge an immediate vet visit.
- Keep responses concise: 3-5 short paragraphs maximum.
- Use bullet points for lists of possible causes or advice.
- If you are unsure, say so honestly and recommend professional consultation.
- NEVER recommend human medications for pets (paracetamol, ibuprofen, etc. are toxic).
- When relevant, suggest the user book an appointment through VetSync.
- Respond in a natural, conversational tone — not robotic or clinical."""


def _get_gemini_client():
    """Lazy-initialize the Gemini client."""
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            print(f"[ASTRID] Gemini init failed: {e}")
            _gemini_client = False  # Mark as failed so we don't retry
    return _gemini_client if _gemini_client else None


def _find_relevant_snippets(message, max_snippets=3):
    """Find vet_med article snippets relevant to the user's message for LLM grounding."""
    kb = _load_kb()
    snippets = kb.get('vet_med_snippets', [])
    if not snippets:
        return []

    words = set(w for w in message.lower().split() if len(w) > 3)
    scored = []
    for s in snippets:
        kw_overlap = len(words & set(s.get('keywords', [])))
        text_hits = sum(1 for w in words if w in s.get('text', '').lower())
        score = kw_overlap * 2 + text_hits
        if score > 0:
            scored.append((score, s['text']))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:max_snippets]]


def _call_gemini_flash(user_message, kb_context="", species=""):
    """Call Gemini Flash with the user message + grounding context."""
    client = _get_gemini_client()
    if not client:
        return None

    # Build context block
    context_parts = []
    if species:
        context_parts.append(f"The user's pet species: {species}")
    if kb_context:
        context_parts.append(f"Relevant veterinary knowledge:\n{kb_context}")

    # Find relevant snippets from vet_med dataset
    snippets = _find_relevant_snippets(user_message)
    if snippets:
        context_parts.append("Additional veterinary reference material:\n" + "\n---\n".join(snippets))

    user_prompt = user_message
    if context_parts:
        user_prompt = "\n\n".join(context_parts) + f"\n\nUser question: {user_message}"

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config={
                "system_instruction": ASTRID_SYSTEM_PROMPT,
                "temperature": 0.7,
                "max_output_tokens": 600,
            }
        )
        return response.text if response.text else None
    except Exception as e:
        print(f"[ASTRID] Gemini call failed: {e}")
        traceback.print_exc()
        return None


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
                 email='demo@vetsync.com', contact='0000000000')
        u.set_password('demo123')
        db.session.add(u)
    db.session.commit()


# ===================== HELPERS =====================

def current_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            flash('Please log in to access that page.', 'error')
            return redirect(url_for('login', next=request.url))
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

# ── Load ASTRID Knowledge Base ────────────────────────────────────────────────

_KB_PATH = os.path.join(os.path.dirname(__file__), 'dataset', 'processed', 'knowledge_base.json')
_KB_DATA  = None

def _load_kb():
    """Lazy-load the knowledge base JSON once."""
    global _KB_DATA
    if _KB_DATA is None:
        if os.path.exists(_KB_PATH):
            with open(_KB_PATH, encoding='utf-8') as f:
                _KB_DATA = json.load(f)
        else:
            _KB_DATA = {'keyword_map': {}, 'knowledge_base': {}}
    return _KB_DATA


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

    # ─── Layer 1: Clinic FAQ ──────────────────────────────────────────────────
    faq_answers = {
        "how to book":      "To book an appointment:\n1. Log in to your account.\n2. Go to your Dashboard.\n3. Click 'Book Appointment'.\n4. Select your pet, service, date, and time slot.",
        "book appointment": "To book an appointment:\n1. Log in to your account.\n2. Go to your Dashboard.\n3. Click 'Book Appointment'.\n4. Select your pet, service, date, and time slot.",
        "clinic hours":     "VetSync Clinic Hours:\n\nMonday - Saturday: 8:00 AM - 6:00 PM\nSunday & Holidays: CLOSED\n\nFor emergencies outside clinic hours, call our 24/7 hotline: (02) 8123-4567",
        "operating hours":  "VetSync Clinic Hours:\n\nMonday - Saturday: 8:00 AM - 6:00 PM\nSunday & Holidays: CLOSED\n\nFor emergencies: (02) 8123-4567",
        "what are the services": "Our services include:\n- General Checkup\n- Vaccination\n- Dental Care\n- Surgery\n- Grooming\n- Emergency Care",
        "services":         "Our services include:\n- General Checkup\n- Vaccination\n- Dental Care\n- Surgery\n- Grooming\n- Emergency Care",
        "sign up":          "To sign up:\n1. Click 'Sign Up' at the top right.\n2. Fill in your name, email, contact, and password.\n3. Log in and start booking for your pet!",
        "register":         "To sign up:\n1. Click 'Sign Up' at the top right.\n2. Fill in your name, email, contact, and password.\n3. Log in and start booking for your pet!",
        "log in":           "To log in: Click 'Log In' on the top right and enter your registered email and password.",
        "login":            "To log in: Click 'Log In' on the top right and enter your registered email and password.",
        "leave a review":   "After completing an appointment, visit your Dashboard and click 'Leave a Review' to share your experience.",
        "contact":          "You can reach VetSync Clinic:\n- Phone: (02) 8123-4567\n- Email: info@vetsync.com\n- Visit our Contact page for the full form.",
        "location":         "Please visit our Contact page or call (02) 8123-4567 for clinic location details.",
        "price":            "Pricing varies by service. Please book a consultation or call (02) 8123-4567 for the latest pricing.",
        "cost":             "Pricing varies by service. Please book a consultation or call (02) 8123-4567 for the latest pricing.",
        "emergency":        "For pet emergencies outside clinic hours, call our 24/7 emergency hotline: (02) 8123-4567. Stay calm, keep your pet comfortable, and get to a vet as soon as possible.",
    }

    for key, answer in faq_answers.items():
        if key in message:
            return jsonify({'reply': answer, 'type': 'faq'})

    # ─── Layer 2: Pet Health Q&A from Knowledge Base ──────────────────────────
    kb      = _load_kb()
    kw_map  = kb.get('keyword_map', {})
    kb_data = kb.get('knowledge_base', {})

    # Find matching symptom key via keyword map
    matched_key = None
    for keyword, kb_key in kw_map.items():
        if keyword in message:
            matched_key = kb_key
            break

    # Also try direct key lookup (e.g. user types exact condition name)
    if not matched_key:
        for kb_key in kb_data:
            if kb_key.replace('_', ' ') in message:
                matched_key = kb_key
                break

    if matched_key and matched_key in kb_data:
        entry  = kb_data[matched_key]
        result = _build_health_reply(entry)
        return jsonify({
            'reply':        result['text'],
            'type':         'health',
            'show_booking': True,
            'condition':    result['condition'],
            'emoji':        result['emoji'],
        })

    # ─── Layer 2.5: VetCare Pro Chatbot Dataset (fuzzy match) ────────────────
    vetcare = kb.get('vetcare_pro', [])
    if vetcare:
        best_match = None
        best_score = 0
        msg_words = set(message.split())

        for entry in vetcare:
            inp_words = set(entry['input'].split())
            overlap = len(msg_words & inp_words)
            # Bonus for longer shared phrases
            if overlap >= 3 or (overlap >= 2 and len(msg_words) <= 5):
                if overlap > best_score:
                    best_score = overlap
                    best_match = entry

        if best_match and best_score >= 2:
            severity = best_match.get('severity', 'medium')
            # Build a rich response
            parts = []

            # Severity banner
            if severity == 'critical':
                parts.append("🚨 EMERGENCY ALERT 🚨")
            elif severity == 'high':
                parts.append("⚠️ URGENT")

            parts.append(best_match['response'])

            if best_match.get('diagnosis') and best_match['diagnosis'] != 'N/A':
                parts.append(f"\nPossible concern: {best_match['diagnosis']}")

            if best_match.get('treatment') and best_match['treatment'] != 'N/A':
                parts.append(f"Recommended action: {best_match['treatment']}")

            parts.append("\n⚕️ This is general guidance only — NOT a substitute for professional veterinary diagnosis.")

            show_booking = severity in ('high', 'critical', 'medium')
            return jsonify({
                'reply':        "\n".join(parts),
                'type':         'vetcare_pro',
                'show_booking': show_booking,
                'severity':     severity,
            })

    # ─── Layer 3: Gemini Flash LLM ─────────────────────────────────────────────
    # Build some KB context for grounding even when no exact match
    kb_context_parts = []
    symptom_history = kb.get('symptom_history', {})
    for symptom, histories in symptom_history.items():
        if symptom in message:
            kb_context_parts.append(f"Symptom '{symptom}' is associated with: {', '.join(histories[:3])}")

    kb_context = "\n".join(kb_context_parts) if kb_context_parts else ""
    species = data.get('species', '')

    llm_reply = _call_gemini_flash(message, kb_context=kb_context, species=species)
    if llm_reply:
        return jsonify({
            'reply':        llm_reply,
            'type':         'llm',
            'show_booking': True,
        })

    # ─── Layer 4: Static Fallback (no API key or LLM failure) ────────────────
    fallback = (
        "I'm ASTRID, your VetSync health assistant!\n\n"
        "I can help with:\n"
        "  - Pet symptoms (vomiting, limping, diarrhea, etc.)\n"
        "  - Emergency cases (hit by car, poisoning, seizures)\n"
        "  - Bird, fish, dog, cat health\n"
        "  - Vaccination, nutrition, medication safety\n"
        "  - Clinic FAQs (booking, hours, services)\n\n"
        "Try asking: 'My dog is vomiting' or 'My fish keeps flipping'\n"
        "Or use the quick reply buttons below."
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
            next_url = request.args.get('next') or url_for('index')
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
    bookings = (Booking.query.filter_by(user_id=user.id)
                .order_by(Booking.created_at.desc()).all())
    return render_template('dashboard.html', user=user, bookings=bookings)


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
