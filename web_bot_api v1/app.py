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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
CORS(app)  # Enable CORS for API endpoints

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7253361872:AAF8m2MtJg3Tfki2-tBsi24HODvKgCfRR1s")

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


# ------------------------------------------------------------------------------
# Data loading with tracking
# ------------------------------------------------------------------------------
def load_json_or_default(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


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


# ------------------------------------------------------------------------------
# Web Interface Routes
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    """Web dashboard"""
    return render_template('dashboard.html')


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
def web_analytics():
    """Web analytics dashboard"""
    web_data = load_json_or_default(WEB_DATA, {})
    activity_data = load_json_or_default(USER_ACTIVITY_FILE, {})
    usage_data = load_json_or_default(APP_USAGE_FILE, {})

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
                           activity_data=activity_data)


# ------------------------------------------------------------------------------
# API Routes
# ------------------------------------------------------------------------------
@app.route('/api/user/register', methods=['POST'])
def register_user():
    """Register a new user with name, semester, and department"""
    data = request.json or {}
    name = data.get('name')
    semester = data.get('semester')
    department = data.get('department')

    if not all([name, semester, department]):
        return jsonify({'success': False, 'error': 'Name, semester, and department are required'})

    # Load existing user data
    web_data = load_json_or_default(WEB_DATA, {})

    # Check if name already exists
    if name in web_data:
        return jsonify({'success': False, 'error': 'User name already exists'})

    # Create user entry with name as parent key
    web_data[name] = {
        'semester': semester,
        'department': department,
        'platform': 'web',
        'registered_at': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'user_id': name
    }

    save_json(web_data, WEB_DATA)

    track_activity(name, 'user_registered', {
        'semester': semester,
        'department': department
    })
    track_app_usage('register_user', name)

    return jsonify({
        'success': True,
        'message': 'User registered successfully',
        'user_name': name,
        'user_id': name
    })


@app.route('/api/user/settings', methods=['GET'])
def get_user_settings():
    """Get user settings by username"""
    username = request.args.get('username')

    if not username:
        return jsonify({'success': False, 'error': 'Username is required'})

    web_data = load_json_or_default(WEB_DATA, {})

    if username not in web_data:
        return jsonify({'success': False, 'error': 'User not found'})

    user_settings = web_data[username]
    return jsonify({'success': True, 'settings': user_settings})


# ------------------------------------------------------------------------------
# MOBILE-FOCUSED LECTURES API ENDPOINTS
# ------------------------------------------------------------------------------

@app.route('/api/mobile/health', methods=['GET'])
def mobile_health_check():
    """Health check endpoint for mobile app"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'lecture_download_api'
    })


@app.route('/api/mobile/semesters', methods=['GET'])
def get_mobile_semesters():
    """Get all available semesters (Mobile optimized)"""
    try:
        semesters = list(semester_subjects.keys())

        return jsonify({
            'success': True,
            'semesters': semesters
        })
    except Exception as e:
        logger.error(f"Error getting semesters: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/mobile/departments', methods=['GET'])
def get_mobile_departments():
    """Get departments for a specific semester (Mobile optimized)"""
    try:
        semester = request.args.get('semester')

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
def get_mobile_subjects():
    """Get subjects for mobile app"""
    try:
        semester = request.args.get('semester')
        department = request.args.get('department')
        user_id = request.args.get('user_id', 'mobile_user')

        if not semester or not department:
            return jsonify({'success': False, 'error': 'Semester and department are required'})

        # Get subjects for the selected semester and department
        semester_data = semester_subjects.get(semester, {})
        department_data = semester_data.get(department, {})

        formatted_subjects = []
        for subject_name, lectures in department_data.items():
            formatted_subjects.append({
                'name': subject_name,
                'lecture_count': len(lectures),
                'total_size_mb': sum(lec.get('file_size_mb', 0) for lec in lectures)
            })

        # Track activity
        track_activity(user_id, 'viewed_subjects', {
            'semester': semester,
            'department': department,
            'subject_count': len(formatted_subjects)
        })
        track_app_usage('mobile_get_subjects', user_id)

        return jsonify({
            'success': True,
            'subjects': formatted_subjects,
            'semester': semester,
            'department': department
        })
    except Exception as e:
        logger.error(f"Error getting subjects: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/mobile/lectures', methods=['GET'])
def get_mobile_lectures():
    """Get lectures for mobile app"""
    try:
        semester = request.args.get('semester')
        department = request.args.get('department')
        subject = request.args.get('subject')
        user_id = request.args.get('user_id', 'mobile_user')

        if not all([semester, department, subject]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})

        lectures = semester_subjects.get(semester, {}).get(department, {}).get(subject, [])

        formatted_lectures = []
        for i, lecture in enumerate(lectures):
            formatted_lectures.append({
                'lecture_id': i,
                'title': lecture.get('file_name', f'Lecture {i + 1}'),
                'type': lecture.get('type', 'document'),
                'file_id': lecture.get('file_id'),
                'file_size_mb': lecture.get('file_size_mb', 0),
                'has_file': bool(lecture.get('file_id')),
                'downloadable': True  # Explicit flag for mobile
            })

        track_activity(user_id, 'viewed_lectures', {
            'subject': subject,
            'lecture_count': len(lectures)
        })
        track_app_usage('mobile_get_lectures', user_id)

        return jsonify({
            'success': True,
            'lectures': formatted_lectures,
            'subject': subject,
            'total_lectures': len(lectures)
        })
    except Exception as e:
        logger.error(f"Error getting lectures: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/mobile/lecture/info', methods=['GET'])
def get_mobile_lecture_info():
    """Get detailed information about a specific lecture"""
    try:
        semester = request.args.get('semester')
        department = request.args.get('department')
        subject = request.args.get('subject')
        lecture_id = request.args.get('lecture_id', type=int)

        if not all([semester, department, subject, lecture_id is not None]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})

        lectures = semester_subjects.get(semester, {}).get(department, {}).get(subject, [])

        if lecture_id >= len(lectures) or lecture_id < 0:
            return jsonify({'success': False, 'error': 'Lecture not found'})

        lecture = lectures[lecture_id]

        lecture_info = {
            'lecture_id': lecture_id,
            'title': lecture.get('file_name'),
            'type': lecture.get('type', 'document'),
            'file_id': lecture.get('file_id'),
            'file_size_mb': lecture.get('file_size_mb', 0),
            'downloadable': bool(lecture.get('file_id')),
            'semester': semester,
            'department': department,
            'subject': subject
        }

        return jsonify({
            'success': True,
            'lecture': lecture_info
        })

    except Exception as e:
        logger.error(f"Error getting lecture info: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/mobile/download', methods=['GET'])
def mobile_download_lecture():
    """Download lecture file for mobile app"""
    try:
        user_id = request.args.get('user_id', 'mobile_user')
        semester = request.args.get('semester')
        department = request.args.get('department')
        subject = request.args.get('subject')
        lecture_id = request.args.get('lecture_id', type=int)

        if not all([user_id, semester, department, subject, lecture_id is not None]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})

        # Find the lecture
        lectures = semester_subjects.get(semester, {}).get(department, {}).get(subject, [])

        if lecture_id >= len(lectures) or lecture_id < 0:
            return jsonify({'success': False, 'error': 'Lecture not found'})

        lecture = lectures[lecture_id]
        file_id = lecture.get('file_id')
        original_file_name = lecture.get('file_name', f'lecture_{lecture_id + 1}')

        if not file_id:
            return jsonify({'success': False, 'error': 'File not available'})

        # Download file from Telegram
        download_result = download_telegram_file(file_id, original_file_name)

        if not download_result['success']:
            return jsonify({'success': False, 'error': download_result['error']})

        file_content = download_result['content']
        file_name = download_result['file_name']

        track_activity(user_id, 'downloaded_lecture', {
            'subject': subject,
            'lecture_id': lecture_id,
            'file_name': file_name,
            'file_size': download_result['file_size']
        })
        track_app_usage('mobile_download_lecture', user_id)

        # Return file as download
        return send_file(
            io.BytesIO(file_content),
            as_attachment=True,
            download_name=file_name,
            mimetype=download_result.get('mime_type', 'application/octet-stream')
        )

    except Exception as e:
        logger.error(f"Mobile download failed: {str(e)}")
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'})


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
        # Get all subjects that have flashcards
        subjects_list = []
        print("Flashcards data:", flashcards_data)  # Debug print

        for subject_name, cards_list in flashcards_data.items():
            # Count total cards for this subject
            total_cards = len(cards_list)

            if total_cards > 0:
                subjects_list.append({
                    'name': subject_name,
                    'card_count': total_cards
                })

        print("Subjects list:", subjects_list)  # Debug print
        return jsonify({
            'success': True,
            'subjects': subjects_list
        })
    except Exception as e:
        logger.error(f"Error loading flashcard subjects: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/flashcards/cards', methods=['GET'])
def get_flashcards():
    """Get all flashcards for a specific subject"""
    subject = request.args.get('subject')

    if not subject:
        return jsonify({'success': False, 'error': 'Subject is required'})

    try:
        print("Looking for subject:", subject)  # Debug print
        print("Available subjects:", list(flashcards_data.keys()))  # Debug print

        if subject not in flashcards_data:
            return jsonify({'success': False, 'error': 'Subject not found'})

        # Get cards for this subject
        cards = flashcards_data[subject]
        print(f"Found {len(cards)} cards for subject {subject}")  # Debug print

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
# Quiz API
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
    """Submit quiz results (read-only - just track, don't save)"""
    data = request.json or {}
    quiz_data = data.get('quiz_data', {})

    if not quiz_data:
        return jsonify({'success': False, 'error': 'Quiz data is required'})

    try:
        # Calculate metrics
        score = quiz_data.get('score', 0)
        total_questions = quiz_data.get('total_questions', 1)
        percentage = (score / total_questions) * 100

        quiz_results = {
            'score': score,
            'total_questions': total_questions,
            'percentage': percentage,
            'subject': quiz_data.get('subject'),
            'timestamp': datetime.now().isoformat()
        }

        # Just return results, don't save to file
        return jsonify({
            'success': True,
            'message': 'Quiz completed successfully',
            'results': quiz_results
        })

    except Exception as e:
        logger.error(f"Error submitting quiz: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


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
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


@app.errorhandler(413)
def too_large(error):
    return jsonify({'success': False, 'error': 'File too large'}), 413


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)