from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, send_file
from flask_cors import CORS
import json
import os
import random
import time
import tempfile
import zipfile
from datetime import datetime
from PIL import Image
import pdf2image
import yt_dlp
from dotenv import load_dotenv
import requests
import io
import logging
from functools import wraps
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import google.generativeai as genai
import asyncio


# Decorator for API responses
#version 6

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(basedir, "users.db")
)


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
app.permanent_session_lifetime = timedelta(minutes=10)
CORS(app)  # Enable CORS for API endpoints

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Gemini AI configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-pro')
else:
    gemini_model = None
    logger.warning("GEMINI_API_KEY not found. AI grading will be disabled for written answers.")

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# File paths
SUBJECTS_JSON = "data/semester_subjects.json"
FLASHCARDS_FILE = "data/flashcards.json"
USER_SETTINGS_FILE = "data/user_setting.json"
WEB_DATA = "data/web_data.json"
USER_ACTIVITY_FILE = "data/user_activity.json"
APP_USAGE_FILE = "data/app_usage.json"


# Database for registration
class User(db.Model):
    id = db.Column("id", db.Integer, primary_key=True)
    username = db.Column("username", db.String(30), nullable=False, unique=True)
    uni_id = db.Column("univicityID", db.Integer)
    password = db.Column("password", db.Integer)
    email = db.Column("email", db.String(100))
    approved = db.Column("approved", db.Boolean, default=False)

    def __init__(self, username, uni_id, password, email, approved):
        self.username = username
        self.uni_id = uni_id
        self.password = password
        self.email = email
        self.approved = approved


# ------------------------------------------------------------------------------
# Data loading with tracking
# ------------------------------------------------------------------------------
def load_json_or_default(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except Exception as e:
        print("JSON load error:", e)
        return default



def save_json(data, path):
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)



def track_activity(user_id, action, details=None):
    """Track user activity for analytics"""
    activity_data = load_json_or_default(USER_ACTIVITY_FILE, {})

    if user_id not in activity_data:
        activity_data[user_id] = {
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'activities': []
        }

    activity_data[user_id]['last_seen'] = datetime.now().isoformat()
    activity_data[user_id]['activities'].append({
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'details': details or {},
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'platform': 'web' if 'web' in request.headers.get('User-Agent', '').lower() else 'mobile'
    })

    # Keep only last 100 activities per user
    activity_data[user_id]['activities'] = activity_data[user_id]['activities'][-100:]

    save_json(activity_data, USER_ACTIVITY_FILE)


def track_app_usage(endpoint, user_id=None):
    """Track API usage statistics"""
    usage_data = load_json_or_default(APP_USAGE_FILE, {})
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in usage_data:
        usage_data[today] = {}

    if endpoint not in usage_data[today]:
        usage_data[today][endpoint] = {
            'count': 0,
            'users': list(),
            'last_used': datetime.now().isoformat()
        }

    usage_data[today][endpoint]['count'] += 1
    usage_data[today][endpoint]['last_used'] = datetime.now().isoformat()

    if user_id:
        usage_data[today][endpoint]['users'].append(str(user_id))

    save_json(usage_data, APP_USAGE_FILE)


# Load initial data
semester_subjects = load_json_or_default(SUBJECTS_JSON, {
    "semester 4": {
        "computer": {
            "Mathematics": [
                {
                    "file_name": "Math Lecture 1.pdf",
                    "file_id": "test_file_1",
                    "type": "document",
                    "file_size_mb": 2.5
                }
            ],
            "Physics": [
                {
                    "file_name": "Physics Lecture 1.pdf",
                    "file_id": "test_file_2",
                    "type": "document",
                    "file_size_mb": 3.1
                }
            ]
        },
        "electronics": {
            "Circuit Analysis": [
                {
                    "file_name": "Circuits Lecture 1.pdf",
                    "file_id": "test_file_3",
                    "type": "document",
                    "file_size_mb": 1.8
                }
            ]
        }
    },
    "semester 5": {
        "computer": {
            "Advanced Programming": [
                {
                    "file_name": "Python Basics.pdf",
                    "file_id": "test_file_4",
                    "type": "document",
                    "file_size_mb": 2.2
                }
            ]
        },
        "electronics": {
            "Digital Electronics": [
                {
                    "file_name": "Digital Logic.pdf",
                    "file_id": "test_file_5",
                    "type": "document",
                    "file_size_mb": 2.8
                }
            ]
        }
    },
    "semester 6": {
        "electronics": {
            "Communication Systems": [
                {
                    "file_name": "Comm Systems 1.pdf",
                    "file_id": "test_file_6",
                    "type": "document",
                    "file_size_mb": 3.5
                }
            ],
            "Signal Processing": [
                {
                    "file_name": "DSP Basics.pdf",
                    "file_id": "test_file_7",
                    "type": "document",
                    "file_size_mb": 2.9
                }
            ]
        }
    }
})

flashcards_data = load_json_or_default(FLASHCARDS_FILE, {})
user_settings = load_json_or_default(USER_SETTINGS_FILE, {})


# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def validate_user_data(user_id):
    if not user_id:
        return False, "User ID is required"
    return True, ""


def get_user_flashcards(user_id, subject=None):
    user_flashcards = {}
    for subj, users in flashcards_data.items():
        if user_id in users:
            if subject:
                if subj == subject:
                    return users[user_id]
            else:
                user_flashcards[subj] = users[user_id]
    return user_flashcards if not subject else []


# ------------------------------------------------------------------------------
# Telegram File Download Functions
# ------------------------------------------------------------------------------
def download_telegram_file(file_id, file_name):
    """Download file from Telegram using file_id"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            return {'success': False, 'error': 'Telegram bot token not configured'}

        # Get file information from Telegram
        file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        file_info_response = requests.get(file_info_url)
        file_info_data = file_info_response.json()

        if not file_info_data.get('ok'):
            return {'success': False, 'error': 'File not found on Telegram'}

        file_path = file_info_data['result']['file_path']

        # Download the actual file
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        file_response = requests.get(download_url)

        if file_response.status_code == 200:
            return {
                'success': True,
                'content': file_response.content,
                'file_name': file_name,
                'file_size': len(file_response.content),
                'mime_type': file_response.headers.get('content-type', 'application/octet-stream')
            }
        else:
            return {'success': False, 'error': f'HTTP {file_response.status_code}'}

    except Exception as e:
        logger.error(f"Error downloading file from Telegram: {str(e)}")
        return {'success': False, 'error': str(e)}


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("logged"):
            flash("You need to login first")
            return redirect(url_for("login"))
        return function(*args, **kwargs)

    return wrapper


# ------------------------------------------------------------------------------
# Gemini AI Functions
# ------------------------------------------------------------------------------
def grade_with_gemini(question, user_answer, correct_answer):
    """Use Gemini AI to grade a written answer"""
    if not gemini_model:
        return {
            'isCorrect': False,
            'confidence': 0.0,
            'feedback': 'AI grading not available. Please check your API key.',
            'error': 'Gemini AI not configured',
            'success': False
        }

    try:
        prompt = f"""
        You are an educational AI assistant grading student answers.

        Question: {question}

        Expected Correct Answer: {correct_answer}

        Student's Answer: {user_answer}

        Instructions:
        1. Compare the student's answer with the expected correct answer.
        2. Be lenient - the student doesn't need to use the exact same wording.
        3. Focus on whether the key concepts are correct.
        4. Consider partial credit for partially correct answers.
        5. Check if the answer is in the correct language (Arabic/English as appropriate).
        6. For Arabic answers, consider synonyms and different phrasing.
        7. For technical answers, focus on accuracy of concepts.
        8. If the answer is mostly correct, mark it as correct.
        9. Only mark as incorrect if the answer is clearly wrong or missing key points.

        Please provide a JSON response with:
        1. isCorrect: true/false (true if the answer is mostly correct, contains key concepts)
        2. confidence: a score from 0.0 to 1.0 indicating how confident you are
        3. feedback: brief, constructive feedback for the student (in the same language as the answer)

        Respond in JSON format only:
        {{
            "isCorrect": boolean,
            "confidence": float,
            "feedback": string
        }}
        """

        response = gemini_model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean the response (remove markdown code blocks if present)
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]
        elif response_text.startswith('```'):
            response_text = response_text[3:-3]

        # Parse JSON response
        result = json.loads(response_text)

        return {
            'isCorrect': result.get('isCorrect', False),
            'confidence': result.get('confidence', 0.0),
            'feedback': result.get('feedback', 'No feedback provided'),
            'success': True
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {response_text}")
        # Fallback: check if answer contains key words
        keywords = correct_answer.lower().split()
        user_lower = user_answer.lower()
        matches = sum(1 for word in keywords if word in user_lower and len(word) > 3)

        is_correct = matches / len(keywords) >= 0.5 if keywords else False

        return {
            'isCorrect': is_correct,
            'confidence': 0.5,
            'feedback': 'AI response parsing failed. Used keyword matching.',
            'success': False
        }
    except Exception as e:
        logger.error(f"Error in AI grading: {str(e)}")
        return {
            'isCorrect': False,
            'confidence': 0.0,
            'feedback': f'AI grading error: {str(e)}',
            'error': str(e),
            'success': False
        }


async def grade_written_answer_async(question, user_answer, correct_answer):
    """Async wrapper for Gemini grading"""
    return grade_with_gemini(question, user_answer, correct_answer)


# ------------------------------------------------------------------------------
# Web Interface Routes
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    """Web dashboard"""
    return render_template('dashboard.html')


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        name = request.form["username"].lower()
        passcode = request.form["password"]
        uni_id = request.form["index"]
        email = request.form["email"]
        does_exists = User.query.filter_by(username=name).first()
        hashed_passcode = bcrypt.generate_password_hash(passcode).decode("utf-8")

        if not name or not passcode or not uni_id or not email:
            flash("All fields are required")
            return redirect(url_for("register"))

        if does_exists:
            flash("username already exists")
            return redirect(url_for("register"))
        else:
            user = User(username=name.lower(), password=hashed_passcode, uni_id=uni_id, email=email, approved=False)
            db.session.add(user)
            db.session.commit()
            flash("registered pending approval")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/admin/pending_users")
@login_required
def pending_users():
    users = User.query.filter_by(approved=False).all()
    admin = session.get("user")
    return render_template("approve.html", users=users, admin=admin)


@app.route("/admin/approve/<int:user_id>")
@login_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.approved = True
    db.session.commit()
    flash(f"User {user.username} approved.")
    return redirect(url_for("pending_users"))


@app.route("/admin/reject/<int:user_id>")
@login_required
def reject_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"User {user.username} deleted.")
    return redirect(url_for("pending_users"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        passcode = request.form["password"]
        database_data = User.query.filter_by(username=username).first()

        if session.get("logged"):
            flash("Already logged in")
            return redirect(url_for("login"))

        if not database_data:
            flash("Wrong username or password or pending approval")
            session["logged"] = False
            session["user"] = None
            return redirect(url_for("login"))

        hashed_password = database_data.password

        if not bcrypt.check_password_hash(hashed_password, passcode) or not database_data.approved:
            flash("Wrong username or password or pending approval")
            session["logged"] = False
            session["user"] = None
            return redirect(url_for("login"))

        # Successful login
        session["logged"] = True
        session["user"] = database_data.username
        app.permanent = True
        return redirect(url_for("web_analytics"))

    return render_template("login.html")

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session["logged"] = False
    session.clear()
    flash("You have been logged out")
    return redirect(url_for("login"))


@app.route('/web/lectures')
def web_lectures():
    """Web interface for lectures"""
    return render_template('lectures.html')


@app.route('/web/flashcards')
def web_flashcards():
    """Web interface for flashcards"""
    return render_template('flashcards.html')


@app.route('/web/quiz')
def web_quiz():
    """Web interface for quiz"""
    return render_template('quiz.html')


@app.route('/web/analytics')
@login_required
def web_analytics():
    """Web analytics dashboard"""
    web_data = load_json_or_default(WEB_DATA, {})
    activity_data = load_json_or_default(USER_ACTIVITY_FILE, {})
    usage_data = load_json_or_default(APP_USAGE_FILE, {})
    admin = session.get("user")

    # Basic analytics
    total_users = len(web_data)
    today_activities = sum(
        len(user_data['activities'])
        for user_data in activity_data.values()
        if any(act['timestamp'].startswith(datetime.now().strftime("%Y-%m-%d"))
               for act in user_data['activities'])
    )

    return render_template('analytics.html',
                           total_users=total_users,
                           today_activities=today_activities,
                           activity_data=activity_data,
                           admin=admin)


# ------------------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------------------
def api_response(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)

            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }), 500

    return wrapper


# Decorator for required parameters
def require_params(*required_params):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # For GET requests, use args; for POST/PUT, use json
            if request.method in ['POST', 'PUT', 'PATCH']:
                data = request.json or request.form
            else:
                data = request.args

            missing = [param for param in required_params if not data.get(param)]

            if missing:
                return jsonify({
                    'success': False,
                    'error': f'Missing required parameters: {", ".join(missing)}'
                }), 400

            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.route('/api/mobile/health', methods=['GET'])
@api_response
def mobile_health_check():
    """Health check endpoint for mobile app"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'lecture_download_api',
        'version': '1.0.0'
    })


@app.route("/api/mobile/login", methods=["POST"])
def mobile_login():
    """Mobile login with username AND password validation"""
    try:
        data = request.get_json(silent=True) or {}

        username = data.get("username", "").strip().lower()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400

        # Check if user exists in the database
        user = User.query.filter_by(username=username).first()

        if not user:
            logger.warning(f"Login failed: User '{username}' not found")
            return jsonify({
                'success': False,
                'error': 'Username or password is incorrect'
            }), 401

        # Verify password - check plain text password against stored hash
        if not bcrypt.check_password_hash(user.password, password):
            logger.warning(f"Login failed: Invalid password for user '{username}'")
            return jsonify({
                'success': False,
                'error': 'Username or password is incorrect'
            }), 401

        # Update user's last login time in the web data storage
        web_data = load_json_or_default(WEB_DATA, {})

        if username not in web_data:
            # Create a basic entry if user exists in User table but not in web_data
            web_data[username] = {
                'semester': 'Not Selected',
                'department': 'Not Selected',
                'platform': 'mobile',
                'registered_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'user_id': username,
                'is_guest': False,
                'username': username
            }
            logger.info(f"Created web_data entry for existing user '{username}'")

        # Update last seen timestamp
        web_data[username]['last_seen'] = datetime.now().isoformat()
        save_json(web_data, WEB_DATA)

        # Track activity
        track_activity(username, 'mobile_login', {'platform': 'mobile'})
        track_app_usage('mobile_login', username)

        logger.info(f"User '{username}' logged in successfully via mobile")

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'username': username
        })

    except Exception as e:
        logger.error(f"Error in mobile_login: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/api/user/login', methods=['POST'])
@api_response
@require_params('username')
def login_user():
    """Login user using username only"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip().lower()

    web_data = load_json_or_default(WEB_DATA, {})

    if username not in web_data:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Update last seen
    web_data[username]['last_seen'] = datetime.now().isoformat()
    save_json(web_data, WEB_DATA)

    track_activity(username, 'user_login', {})
    track_app_usage('login_user', username)

    return jsonify({
        'success': True,
        'message': 'Login successful',
        'settings': web_data[username]
    })


@app.route('/api/user/register', methods=['POST'])
@api_response
@require_params('name', 'semester', 'department')
def register_user():
    data = request.get_json(silent=True) or {}

    name = data.get('name', '').strip().lower()
    semester = data.get('semester')
    department = data.get('department')
    is_mobile = bool(data.get("platform_is_mobile", False))
    is_guest = bool(data.get("is_guest", False))
    platform = "mobile" if is_mobile else "web"

    web_data = load_json_or_default(WEB_DATA, {})

    if name in web_data:
        return jsonify({'success': False, 'error': 'User name already exists'}), 409

    user_data = {
        'semester': semester,
        'department': department,
        'platform': platform,
        'registered_at': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'user_id': name,
        'username': name  # Add username field for consistency
    }

    if is_guest:
        user_data['is_guest'] = True
        user_data['can_upgrade'] = True  # Flag for frontend

    web_data[name] = user_data
    save_json(web_data, WEB_DATA)

    track_activity(name, 'user_registered', {
        'platform': platform,
        'is_guest': is_guest
    })

    return jsonify({
        'success': True,
        'message': 'User registered successfully',
        'user_name': name,
        'user_id': name,
        'is_guest': is_guest
    })


@app.route('/api/user/update', methods=['POST'])
@api_response
@require_params('name', 'semester', 'department')
def update_user_settings():
    data = request.get_json(silent=True) or {}
    old_name = data.get('old_name', '').strip().lower()
    new_name = data.get('name', '').strip().lower()
    semester = data.get('semester')
    department = data.get('department')
    upgrade = data.get('upgrade', False)

    web_data = load_json_or_default(WEB_DATA, {})

    # Guest → Real account upgrade
    if upgrade:
        if old_name not in web_data:
            return jsonify({'success': False, 'error': 'Guest user not found'}), 404

        if new_name in web_data and new_name != old_name:
            return jsonify({'success': False, 'error': 'Username already exists'}), 409

        # Move guest data → real account
        user_data = web_data.pop(old_name)

        user_data.update({
            'semester': semester,
            'department': department,
            'is_guest': False,
            'can_upgrade': False,
            'last_seen': datetime.now().isoformat(),
            'username': new_name  # Update username field
        })

        web_data[new_name] = user_data
        save_json(web_data, WEB_DATA)

        track_activity(new_name, 'guest_upgraded', {
            'from': old_name,
            'semester': semester,
            'department': department
        })

        return jsonify({
            'success': True,
            'message': 'Guest upgraded to real account',
            'new_username': new_name
        })

    # Normal user update
    if new_name not in web_data:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    web_data[new_name].update({
        'semester': semester,
        'department': department,
        'last_seen': datetime.now().isoformat()
    })

    save_json(web_data, WEB_DATA)

    track_activity(new_name, 'user_updated', {
        'semester': semester,
        'department': department
    })

    return jsonify({
        'success': True,
        'message': 'User updated successfully'
    })


@app.route('/api/user/settings', methods=['GET'])
@api_response
@require_params('username')
def get_user_settings():
    """Get user settings by username"""
    username = request.args.get('username', '').strip().lower()

    web_data = load_json_or_default(WEB_DATA, {})

    if username not in web_data:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    user_settings = web_data[username]
    return jsonify({'success': True, 'settings': user_settings})


@app.route('/api/mobile/semesters', methods=['GET'])
@api_response
def get_mobile_semesters():
    """Get all available semesters"""
    try:
        semesters = list(semester_subjects.keys())
        return jsonify({
            'success': True,
            'semesters': semesters,
            'count': len(semesters)
        })
    except Exception as e:
        logger.error(f"Error getting semesters: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to fetch semesters'}), 500


@app.route('/api/mobile/departments', methods=['GET'])
@api_response
def get_mobile_departments():
    """Get departments for a specific semester (Mobile optimized)"""
    try:
        semester = request.args.get('semester')  # GET request uses args, not json

        if not semester:
            return jsonify({'success': False, 'error': 'Semester parameter is required'})

        if semester not in semester_subjects:
            return jsonify({'success': False, 'error': 'Semester not found'})

        departments = list(semester_subjects[semester].keys())

        return jsonify({
            'success': True,
            'departments': departments,
            'semester': semester
        })
    except Exception as e:
        logger.error(f"Error getting departments: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mobile/subjects', methods=['GET'])
@api_response
@require_params('semester', 'department')
def get_mobile_subjects():
    """Get subjects for mobile app"""
    semester = request.args.get('semester')
    department = request.args.get('department')
    user_id = request.args.get('user_id', 'mobile_user')

    if semester not in semester_subjects:
        return jsonify({'success': False, 'error': 'Semester not found'}), 404

    if department not in semester_subjects[semester]:
        return jsonify({'success': False, 'error': 'Department not found'}), 404

    subjects_data = semester_subjects[semester][department]
    formatted_subjects = []

    for subject_name, lectures in subjects_data.items():
        formatted_subjects.append({
            'name': subject_name,
            'lecture_count': len(lectures),
            'total_size_mb': round(sum(lec.get('file_size_mb', 0) for lec in lectures), 2),
            'has_files': any(lec.get('file_id') for lec in lectures)
        })

    track_activity(user_id, 'viewed_subjects', {
        'semester': semester,
        'department': department,
        'subject_count': len(formatted_subjects)
    })

    return jsonify({
        'success': True,
        'subjects': formatted_subjects,
        'semester': semester,
        'department': department,
        'total_subjects': len(formatted_subjects)
    })


@app.route('/api/mobile/lectures', methods=['GET'])
@api_response
@require_params('semester', 'department', 'subject')
def get_mobile_lectures():
    """Get lectures for mobile app"""
    semester = request.args.get('semester')
    department = request.args.get('department')
    subject = request.args.get('subject')
    user_id = request.args.get('user_id', 'mobile_user')

    # Validate semester, department, and subject
    try:
        lectures = semester_subjects[semester][department][subject]
    except KeyError:
        return jsonify({'success': False, 'error': 'Subject not found'}), 404

    formatted_lectures = []
    for i, lecture in enumerate(lectures):
        formatted_lectures.append({
            'lecture_id': i,
            'title': lecture.get('file_name', f'Lecture {i + 1}'),
            'type': lecture.get('type', 'document'),
            'file_id': lecture.get('file_id'),
            'file_size_mb': round(lecture.get('file_size_mb', 0), 2),
            'has_file': bool(lecture.get('file_id')),
            'downloadable': bool(lecture.get('file_id')),
            'extension': lecture.get('extension', '').lower(),
            'upload_date': lecture.get('upload_date')
        })

    track_activity(user_id, 'viewed_lectures', {
        'subject': subject,
        'lecture_count': len(lectures)
    })

    return jsonify({
        'success': True,
        'lectures': formatted_lectures,
        'subject': subject,
        'total_lectures': len(formatted_lectures),
        'downloadable_count': sum(1 for l in formatted_lectures if l['downloadable'])
    })


@app.route('/api/mobile/lecture/info', methods=['GET'])
@api_response
@require_params('semester', 'department', 'subject', 'lecture_id')
def get_mobile_lecture_info():
    """Get detailed information about a specific lecture"""
    semester = request.args.get('semester')
    department = request.args.get('department')
    subject = request.args.get('subject')
    lecture_id = int(request.args.get('lecture_id'))

    try:
        lectures = semester_subjects[semester][department][subject]
    except KeyError:
        return jsonify({'success': False, 'error': 'Invalid parameters'}), 400

    if lecture_id >= len(lectures) or lecture_id < 0:
        return jsonify({'success': False, 'error': 'Lecture not found'}), 404

    lecture = lectures[lecture_id]

    lecture_info = {
        'lecture_id': lecture_id,
        'title': lecture.get('file_name'),
        'type': lecture.get('type', 'document'),
        'file_id': lecture.get('file_id'),
        'file_size_mb': round(lecture.get('file_size_mb', 0), 2),
        'downloadable': bool(lecture.get('file_id')),
        'semester': semester,
        'department': department,
        'subject': subject,
        'extension': lecture.get('extension', ''),
        'upload_date': lecture.get('upload_date'),
        'description': lecture.get('description', '')
    }

    return jsonify({
        'success': True,
        'lecture': lecture_info
    })


@app.route('/api/mobile/download', methods=['GET'])
@api_response
@require_params('semester', 'department', 'subject', 'lecture_id')
def mobile_download_lecture():
    """Download lecture file for mobile app"""
    user_id = request.args.get('user_id', 'mobile_user')
    semester = request.args.get('semester')
    department = request.args.get('department')
    subject = request.args.get('subject')
    lecture_id = int(request.args.get('lecture_id'))

    # Find the lecture
    try:
        lectures = semester_subjects[semester][department][subject]
    except KeyError:
        return jsonify({'success': False, 'error': 'Invalid parameters'}), 400

    if lecture_id >= len(lectures) or lecture_id < 0:
        return jsonify({'success': False, 'error': 'Lecture not found'}), 404

    lecture = lectures[lecture_id]
    file_id = lecture.get('file_id')
    original_file_name = lecture.get('file_name', f'lecture_{lecture_id + 1}')

    if not file_id:
        return jsonify({'success': False, 'error': 'File not available for download'}), 404

    # Download file from Telegram
    download_result = download_telegram_file(file_id, original_file_name)

    if not download_result['success']:
        return jsonify({'success': False, 'error': download_result['error']}), 500

    file_content = download_result['content']
    file_name = download_result['file_name']
    mime_type = download_result.get('mime_type', 'application/octet-stream')

    track_activity(user_id, 'downloaded_lecture', {
        'subject': subject,
        'lecture_id': lecture_id,
        'file_name': file_name,
        'file_size': download_result.get('file_size', 0)
    })

    # Return file as download with proper headers
    return send_file(
        io.BytesIO(file_content),
        as_attachment=True,
        download_name=file_name,
        mimetype=mime_type,
        last_modified=datetime.now()
    )

# ------------------------------------------------------------------------------
# ORIGINAL LECTURES API (Web + Mobile)
# ------------------------------------------------------------------------------
@app.route('/api/lectures/subjects', methods=['GET'])
def get_subjects():
    """Get subjects for user (Mobile & Web)"""
    username = request.args.get('username')
    semester = request.args.get('semester')
    department = request.args.get('department')

    print(f"DEBUG - Username: {username}, Semester: {semester}, Department: {department}")

    web_data = load_json_or_default(WEB_DATA, {})

    # If semester/department not provided, try to get from user settings
    if not semester or not department:
        if username and username != 'guest' and username in web_data:
            user_data = web_data[username]
            semester = user_data.get('semester')
            department = user_data.get('department')
            print(f"DEBUG - Using saved user settings: {semester}, {department}")

    if not semester or not department:
        return jsonify({'success': False, 'error': 'Semester and department are required'})

    # Get subjects for the selected semester and department
    semester_data = semester_subjects.get(semester, {})
    department_data = semester_data.get(department, {})

    print(f"DEBUG - Found {len(department_data)} subjects for {semester} - {department}")

    formatted_subjects = []
    for subject_name, lectures in department_data.items():
        formatted_subjects.append({
            'name': subject_name,
            'lecture_count': len(lectures),
            'total_size_mb': sum(lec.get('file_size_mb', 0) for lec in lectures)
        })

    # Track activity for both registered and guest users
    user_to_track = username if username and username != 'guest' else 'guest_user'
    track_activity(user_to_track, 'viewed_subjects', {
        'semester': semester,
        'department': department,
        'subject_count': len(formatted_subjects)
    })
    track_app_usage('get_subjects', user_to_track)

    return jsonify({
        'success': True,
        'subjects': formatted_subjects,
        'semester': semester,
        'department': department
    })


@app.route('/api/lectures/lectures', methods=['GET'])
def get_lectures():
    """Get lectures for a specific subject (Mobile & Web)"""
    username = request.args.get('username')
    semester = request.args.get('semester')
    department = request.args.get('department')
    subject = request.args.get('subject')

    if not all([semester, department, subject]):
        return jsonify({'success': False, 'error': 'Missing required parameters'})

    lectures = semester_subjects.get(semester, {}).get(department, {}).get(subject, [])

    formatted_lectures = []
    for i, lecture in enumerate(lectures):
        formatted_lectures.append({
            'id': i,
            'title': lecture.get('file_name', f'Lecture {i + 1}'),
            'type': lecture.get('type', 'document'),
            'file_id': lecture.get('file_id'),
            'file_size_mb': lecture.get('file_size_mb', 0),
            'has_file': bool(lecture.get('file_id'))
        })

    track_activity(username or 'guest', 'viewed_lectures', {
        'subject': subject,
        'lecture_count': len(lectures)
    })
    track_app_usage('get_lectures', username or 'guest')

    return jsonify({
        'success': True,
        'lectures': formatted_lectures,
        'subject': subject,
        'total_lectures': len(lectures)
    })


# ------------------------------------------------------------------------------
# File Download Endpoint
# ------------------------------------------------------------------------------
@app.route('/api/lectures/download/<int:lecture_id>', methods=['GET'])
def download_lecture(lecture_id):
    """Download lecture file from Telegram"""
    username = request.args.get('username')
    semester = request.args.get('semester')
    department = request.args.get('department')
    subject = request.args.get('subject')

    if not all([username, semester, department, subject]):
        return jsonify({'success': False, 'error': 'Missing required parameters'})

    # Find the lecture
    lectures = semester_subjects.get(semester, {}).get(department, {}).get(subject, [])

    if lecture_id >= len(lectures) or lecture_id < 0:
        return jsonify({'success': False, 'error': 'Lecture not found'})

    lecture = lectures[lecture_id]
    file_id = lecture.get('file_id')
    original_file_name = lecture.get('file_name', f'Lecture {lecture_id + 1}')

    if not file_id:
        return jsonify({'success': False, 'error': 'File not available'})

    try:
        # Download file from Telegram
        download_result = download_telegram_file(file_id, original_file_name)

        if not download_result['success']:
            return jsonify({'success': False, 'error': download_result['error']})

        file_content = download_result['content']
        download_filename = original_file_name

        track_activity(username, 'downloaded_lecture', {
            'subject': subject,
            'lecture_id': lecture_id,
            'file_name': original_file_name,
            'file_size': download_result['file_size']
        })
        track_app_usage('download_lecture', username)

        # Return file as download with original name
        return send_file(
            io.BytesIO(file_content),
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/octet-stream'
        )

    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'})


# ------------------------------------------------------------------------------
# Analytics API
# ------------------------------------------------------------------------------
@app.route('/api/analytics/overview', methods=['GET'])
def get_analytics_overview():
    """Get analytics overview for dashboard"""
    web_data = load_json_or_default(WEB_DATA, {})
    telegram_data = load_json_or_default(USER_SETTINGS_FILE, {})
    activity_data = load_json_or_default(USER_ACTIVITY_FILE, {})
    usage_data = load_json_or_default(APP_USAGE_FILE, {})

    # Calculate metrics
    web_users = len(web_data)
    telegram_users = len(telegram_data)
    total_users = web_users + telegram_users
    today = datetime.now().strftime("%Y-%m-%d")

    # Active users today
    active_today = len([
        user_id for user_id, user_data in activity_data.items()
        if any(act['timestamp'].startswith(today) for act in user_data.get('activities', []))
    ])

    # Platform distribution - Count UNIQUE USERS by platform
    platforms = {'web': 0, 'telegram': 0, 'mobile': 0}

    # Count unique users from web_data (web users)
    platforms['web'] = len(web_data)

    # Count unique users from telegram_data (telegram users)
    platforms['telegram'] = len(telegram_data)

    # Count mobile users from activity data (users with mobile activities)
    mobile_users = set()
    for user_id, user_data in activity_data.items():
        for activity in user_data.get('activities', []):
            if activity.get('platform') == 'mobile':
                mobile_users.add(user_id)
    platforms['mobile'] = len(mobile_users)

    # Platform activity distribution (for activity counts)
    platform_activities = {'web': 0, 'telegram': 0, 'mobile': 0}
    for user_data in activity_data.values():
        for activity in user_data.get('activities', []):
            platform = activity.get('platform', 'web')
            platform_activities[platform] = platform_activities.get(platform, 0) + 1

    # Popular endpoints
    endpoint_usage = {}
    for date, endpoints in usage_data.items():
        for endpoint, data in endpoints.items():
            if endpoint not in endpoint_usage:
                endpoint_usage[endpoint] = 0
            endpoint_usage[endpoint] += data['count']

    popular_endpoints = dict(sorted(endpoint_usage.items(), key=lambda x: x[1], reverse=True)[:5])

    # Total activities
    total_activities = sum(len(user_data.get('activities', [])) for user_data in activity_data.values())

    return jsonify({
        'success': True,
        'analytics': {
            'total_users': total_users,
            'web_users': web_users,
            'telegram_users': telegram_users,
            'active_today': active_today,
            'user_breakdown': platforms,  # Unique users by platform
            'platform_distribution': platforms,  # Keep both for backward compatibility
            'platform_activities': platform_activities,  # Activity counts by platform
            'popular_endpoints': popular_endpoints,
            'total_activities': total_activities,
            'users_with_profile': web_users
        }
    })


@app.route('/api/analytics/user-activity-detailed', methods=['GET'])
def get_detailed_user_activity():
    """Get detailed user activity with user information"""
    try:
        web_data = load_json_or_default(WEB_DATA, {})
        activity_data = load_json_or_default(USER_ACTIVITY_FILE, {})
        telegram_data = load_json_or_default(USER_SETTINGS_FILE, {})

        # Combine web users and activity data
        detailed_users = []

        # Process web users
        for username, user_info in web_data.items():
            user_activities = activity_data.get(username, {})
            activities_count = len(user_activities.get('activities', []))
            last_seen = user_activities.get('last_seen', user_info.get('last_seen', 'Never'))

            detailed_users.append({
                'user_id': username,
                'name': username,
                'platform': 'web',
                'semester': user_info.get('semester', 'Not set'),
                'department': user_info.get('department', 'Not set'),
                'last_activity': last_seen,
                'activity_count': activities_count,
                'registered_at': user_info.get('registered_at', 'Unknown'),
                'activities': user_activities.get('activities', [])[-5:]  # Last 5 activities
            })

        # Process telegram users (from user_settings)
        for user_id, user_settings in telegram_data.items():
            user_activities = activity_data.get(user_id, {})
            activities_count = len(user_activities.get('activities', []))
            last_seen = user_activities.get('last_seen', 'Never')

            # Get semester and department from telegram user settings
            semester = user_settings.get('semester', 'Not set')
            department = user_settings.get('department', 'Not set')

            detailed_users.append({
                'user_id': user_id,
                'name': f"Telegram User {user_id}",
                'platform': 'telegram',
                'semester': semester,
                'department': department,
                'last_activity': last_seen,
                'activity_count': activities_count,
                'registered_at': 'Unknown',
                'activities': user_activities.get('activities', [])[-5:]
            })

        # Process mobile users from activity data that aren't in web or telegram
        mobile_users_processed = set()
        for user_id, user_activities in activity_data.items():
            if user_id not in web_data and user_id not in telegram_data:
                # Check if user has mobile activities
                has_mobile_activities = any(
                    act.get('platform') == 'mobile'
                    for act in user_activities.get('activities', [])
                )

                if has_mobile_activities and user_id not in mobile_users_processed:
                    activities_count = len(user_activities.get('activities', []))
                    last_seen = user_activities.get('last_seen', 'Never')

                    detailed_users.append({
                        'user_id': user_id,
                        'name': f"Mobile User {user_id}",
                        'platform': 'mobile',
                        'semester': 'Not set',
                        'department': 'Not set',
                        'last_activity': last_seen,
                        'activity_count': activities_count,
                        'registered_at': 'Unknown',
                        'activities': user_activities.get('activities', [])[-5:]
                    })
                    mobile_users_processed.add(user_id)

        # Sort by last activity (most recent first)
        detailed_users.sort(key=lambda x: x['last_activity'] if x['last_activity'] != 'Never' else '', reverse=True)

        return jsonify({
            'success': True,
            'users': detailed_users,
            'total_users': len(detailed_users)
        })

    except Exception as e:
        logger.error(f"Error loading detailed user activity: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/flashcards/subjects', methods=['GET'])
def get_flashcard_subjects():
    """Get all available subjects from flashcards data"""
    try:
        # Load flashcards data fresh
        flashcards_data = load_json_or_default(FLASHCARDS_FILE, {})

        # Debug log
        print(f"DEBUG - Loading subjects from flashcards data")
        print(f"DEBUG - Keys in flashcards_data: {list(flashcards_data.keys())}")

        # Get all subjects that have flashcards
        subjects_list = []

        for subject_name, cards_list in flashcards_data.items():
            # Check if it's a valid subject with cards
            if isinstance(cards_list, list):
                total_cards = len(cards_list)
                print(f"DEBUG - Subject: {subject_name}, Cards: {total_cards}")

                if total_cards > 0:
                    subjects_list.append({
                        'name': subject_name,
                        'card_count': total_cards
                    })
            else:
                print(f"DEBUG - Skipping {subject_name}, not a list: {type(cards_list)}")

        print(f"DEBUG - Subjects found: {subjects_list}")  # Debug print

        if not subjects_list:
            # Try alternative structure
            print(f"DEBUG - Trying alternative structure...")
            for subject_name, users_dict in flashcards_data.items():
                if isinstance(users_dict, dict):
                    for user_id, user_cards in users_dict.items():
                        if isinstance(user_cards, list):
                            total_cards = len(user_cards)
                            if total_cards > 0:
                                subjects_list.append({
                                    'name': subject_name,
                                    'card_count': total_cards
                                })
                                break

        return jsonify({
            'success': True,
            'subjects': subjects_list,
            'total_subjects': len(subjects_list)
        })
    except Exception as e:
        logger.error(f"Error loading flashcard subjects: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'subjects': [],
            'message': 'No flashcards found. Please create flashcards first.'
        })


@app.route('/api/debug/flashcards_structure', methods=['GET'])
def debug_flashcards_structure():
    """Debug endpoint to check flashcards data structure"""
    try:
        flashcards_data = load_json_or_default(FLASHCARDS_FILE, {})

        structure_info = {
            'file_path': FLASHCARDS_FILE,
            'exists': os.path.exists(FLASHCARDS_FILE),
            'keys': list(flashcards_data.keys()),
            'total_keys': len(flashcards_data),
            'sample_structure': {}
        }

        # Sample first few items
        for i, (key, value) in enumerate(list(flashcards_data.items())[:3]):
            structure_info['sample_structure'][key] = {
                'type': type(value).__name__,
                'length': len(value) if hasattr(value, '__len__') else 'N/A',
                'first_item': value[0] if isinstance(value, list) and len(value) > 0 else 'N/A'
            }

        return jsonify({
            'success': True,
            'debug_info': structure_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/flashcards/cards', methods=['GET'])
def get_flashcards():
    """Get all flashcards for a specific subject"""
    subject = request.args.get('subject')

    if not subject:
        return jsonify({'success': False, 'error': 'Subject is required'})

    try:
        if subject not in flashcards_data:
            return jsonify({'success': False, 'error': 'Subject not found'})

        # Get cards for this subject
        cards = flashcards_data[subject]

        # Add missing fields to cards
        formatted_cards = []
        for i, card in enumerate(cards):
            formatted_card = card.copy()
            formatted_card['card_id'] = f"card_{i + 1}"
            formatted_card['timestamp'] = datetime.now().isoformat()
            formatted_cards.append(formatted_card)

        return jsonify({
            'success': True,
            'cards': formatted_cards,
            'total_cards': len(formatted_cards),
            'subject': subject
        })
    except Exception as e:
        logger.error(f"Error loading flashcards: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# ------------------------------------------------------------------------------
# Quiz API with Gemini AI Integration
# ------------------------------------------------------------------------------
@app.route('/api/quiz/start', methods=['POST'])
def start_quiz():
    """Start a new quiz session using existing flashcards"""
    data = request.json or {}
    subject = data.get('subject')
    question_count = data.get('question_count', 10)
    quiz_type = data.get('type', 'multiple_choice')

    if not subject:
        return jsonify({'success': False, 'error': 'Subject is required'})

    try:
        if subject not in flashcards_data:
            return jsonify({'success': False, 'error': 'Subject not found'})

        # Get all cards for the subject
        all_cards = flashcards_data[subject]

        if not all_cards:
            return jsonify({'success': False, 'error': 'No flashcards found for this subject'})

        # Generate quiz questions
        quiz_questions = []

        # Make sure we don't request more questions than available cards
        actual_question_count = min(question_count, len(all_cards))

        # Randomly select cards for the quiz
        selected_cards = random.sample(all_cards, actual_question_count)

        for card in selected_cards:
            if quiz_type == 'multiple_choice':
                # Create multiple choice question
                question = {
                    'question': card['question'],
                    'type': 'multiple_choice',
                    'correct_answer': card['answer'],
                    'options': generate_multiple_choice_options(card['answer'], all_cards)
                }
            else:
                # Create written answer question
                question = {
                    'question': card['question'],
                    'type': 'written',
                    'correct_answer': card['answer']
                }

            quiz_questions.append(question)

        # Create quiz session
        quiz_session = {
            'session_id': f"quiz_{int(time.time())}",
            'subject': subject,
            'type': quiz_type,
            'start_time': datetime.now().isoformat(),
            'total_questions': len(quiz_questions)
        }

        return jsonify({
            'success': True,
            'questions': quiz_questions,
            'quiz_session': quiz_session
        })

    except Exception as e:
        logger.error(f"Error starting quiz: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/quiz/submit', methods=['POST'])
def submit_quiz():
    """Submit quiz results with optional AI grading for written answers"""
    data = request.json or {}
    quiz_data = data.get('quiz_data', {})

    if not quiz_data:
        return jsonify({'success': False, 'error': 'Quiz data is required'})

    try:
        answers = quiz_data.get('answers', [])
        total_questions = quiz_data.get('total_questions', len(answers))

        # Calculate initial score
        score = sum(1 for answer in answers if answer.get('isCorrect', False))

        # Check if we need to grade written answers
        written_answers = [answer for answer in answers if answer.get('type') == 'written']

        if written_answers and gemini_model:
            # Grade written answers with AI
            for answer in written_answers:
                ai_result = grade_with_gemini(
                    answer['question'],
                    answer['userAnswer'],
                    answer.get('correctAnswer', '')
                )

                if ai_result.get('success', False):
                    answer['isCorrect'] = ai_result['isCorrect']
                    answer['confidence'] = ai_result['confidence']
                    answer['feedback'] = ai_result['feedback']
                    answer['ai_graded'] = True

                    # Update score based on AI grading
                    if answer['isCorrect'] and not answer.get('previouslyCorrect', False):
                        score += 1
                    elif not answer['isCorrect'] and answer.get('previouslyCorrect', False):
                        score -= 1
                else:
                    answer['ai_graded'] = False
                    answer['feedback'] = ai_result.get('feedback', 'AI grading failed')

        percentage = (score / total_questions) * 100

        quiz_results = {
            'score': score,
            'total_questions': total_questions,
            'percentage': percentage,
            'subject': quiz_data.get('subject'),
            'timestamp': datetime.now().isoformat(),
            'answers': answers  # Include graded answers in response
        }

        return jsonify({
            'success': True,
            'message': 'Quiz completed successfully',
            'results': quiz_results,
            'ai_grading_used': gemini_model is not None and len(written_answers) > 0
        })

    except Exception as e:
        logger.error(f"Error submitting quiz: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/quiz/grade_written', methods=['POST'])
def grade_written_answer():
    """Grade a single written answer using AI"""
    data = request.json or {}

    question = data.get('question')
    user_answer = data.get('user_answer')
    correct_answer = data.get('correct_answer')

    if not all([question, user_answer, correct_answer]):
        return jsonify({'success': False, 'error': 'Missing required fields'})

    if not gemini_model:
        return jsonify({
            'success': False,
            'error': 'AI grading not available',
            'isCorrect': False,
            'feedback': 'AI service not configured. Please check your Gemini API key.'
        })

    try:
        result = grade_with_gemini(question, user_answer, correct_answer)
        return jsonify({
            'success': True,
            'isCorrect': result['isCorrect'],
            'confidence': result['confidence'],
            'feedback': result['feedback'],
            'ai_graded': True
        })

    except Exception as e:
        logger.error(f"Error grading answer with AI: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'isCorrect': False,
            'feedback': f'Error: {str(e)}'
        })


def generate_multiple_choice_options(correct_answer, all_cards):
    """Generate multiple choice options including the correct answer"""
    options = [correct_answer]

    # Get wrong answers from other cards
    wrong_answers = []
    for card in all_cards:
        if card['answer'] != correct_answer and card['answer'] not in wrong_answers:
            wrong_answers.append(card['answer'])

    # Shuffle and pick 3 wrong answers
    random.shuffle(wrong_answers)
    options.extend(wrong_answers[:3])

    # Shuffle all options
    random.shuffle(options)
    return options


# ------------------------------------------------------------------------------
# Error Handlers
# ------------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(error):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({
            "error": "Endpoint not found",
            "success": False
        }), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
    return render_template("500.html"), 500


@app.errorhandler(413)
def too_large(error):
    return jsonify({'success': False, 'error': 'File too large'}), 413


if __name__ == '__main__':
    # To run inside this code only
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)