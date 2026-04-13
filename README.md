# VetSync Clinic Platform

Welcome to VetSync Clinic, a comprehensive veterinary appointment booking and management platform. This system is designed for ease of use, featuring a modern interface for clients and a helpful scripted assistant, ASTRID.

---

## 🚀 Getting Started (For Groupmates)

To run this project locally on your machine, follow these steps:

### 1. Clone the Repository
```bash
git clone https://github.com/0323DxD/vetsync.git
cd vetsync
```

### 2. Set Up a Virtual Environment
It is recommended to use a virtual environment to keep dependencies organized:
```bash
# Create venv
python -m venv venv

# Activate venv (Windows)
.\venv\Scripts\activate

# Activate venv (Mac/Linux)
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```
The app will be available at `http://127.0.0.1:5000`.

---

## 💬 ASTRID Virtual Assistant
ASTRID is our scripted help assistant. 
- **Location**: Click the floating blue chat button at the bottom right.
- **Function**: It provides quick, guided answers to common questions (Sign up, Booking, Offers, etc.) via multiple-choice buttons.
- **No API Key Needed**: This version is fully scripted and does not require external AI services or API keys to run.

---

## 🛠️ Project Structure
- `app.py`: Main Flask application logic and database models.
- `templates/`: HTML templates (Base, Index, Booking, Chatbot, etc.).
- `static/`: CSS styling and images.
- `requirements.txt`: List of Python libraries required.

*(Enjoy collaborating on VetSync!)*

