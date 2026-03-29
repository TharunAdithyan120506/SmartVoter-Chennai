"""Authentication routes: OTP login, admin login, logout."""
import hashlib
import random
import string
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, session
from db import query_one, query_all, execute, call_procedure, get_db
from config import Config

auth_bp = Blueprint('auth', __name__)


def voter_required(f):
    """Middleware: require voter session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'voter_id' not in session:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Middleware: require admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'success': False, 'error': 'Admin authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def hash_otp(otp):
    """SHA-256 hash of OTP string."""
    return hashlib.sha256(otp.encode()).hexdigest()


@auth_bp.route('/auth/send-otp', methods=['POST'])
def send_otp():
    """Step 1 of voter login: send OTP to voter's phone."""
    data = request.get_json()
    if not data or 'aadhar' not in data:
        return jsonify({'success': False, 'error': 'Aadhar number is required'}), 400

    aadhar = data['aadhar'].replace(' ', '')
    if len(aadhar) != 12 or not aadhar.isdigit():
        return jsonify({'success': False, 'error': 'Invalid Aadhar number format'}), 400

    # Look up voter by aadhar
    voter = query_one("SELECT voter_id, name, phone FROM voters WHERE aadhar = %s", (aadhar,))
    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found with this Aadhar number'}), 404

    # Generate 6-digit OTP
    otp = ''.join(random.choices(string.digits, k=6))
    otp_hashed = hash_otp(otp)

    # Generate session_id and store OTP session using inline SQL
    # (avoids MySQL OUT parameter retrieval issues with mysql-connector)
    session_id = str(uuid.uuid4())
    db = get_db()
    cursor = db.cursor()

    # Expire old sessions for this aadhar
    cursor.execute(
        "UPDATE otp_sessions SET is_used = TRUE WHERE aadhar = %s AND is_used = FALSE",
        (aadhar,)
    )

    # Insert new session with 10-minute expiry
    cursor.execute(
        "INSERT INTO otp_sessions (session_id, aadhar, otp_hash, expires_at) "
        "VALUES (%s, %s, %s, DATE_ADD(NOW(), INTERVAL 10 MINUTE))",
        (session_id, aadhar, otp_hashed)
    )
    cursor.close()

    # Mask phone number
    phone = voter['phone']
    masked_phone = 'XXXXX' + phone[-5:] if len(phone) >= 5 else phone

    response = {
        'success': True,
        'session_id': session_id,
        'masked_phone': masked_phone,
        'message': f'OTP sent to {masked_phone}'
    }

    # In mock mode, include OTP in response
    if Config.MOCK_OTP:
        response['otp'] = otp
        print(f"[MOCK OTP] Aadhar: {aadhar} → OTP: {otp}")

    return jsonify(response)


@auth_bp.route('/auth/verify-otp', methods=['POST'])
def verify_otp():
    """Step 2 of voter login: verify OTP and create session."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    aadhar = data.get('aadhar', '').replace(' ', '')
    session_id = data.get('session_id', '')
    otp = data.get('otp', '')

    if not all([aadhar, session_id, otp]):
        return jsonify({'success': False, 'error': 'Aadhar, session_id, and OTP are required'}), 400

    # Validate OTP session
    otp_session = query_one(
        """SELECT session_id, otp_hash, is_used, attempts, expires_at
           FROM otp_sessions
           WHERE session_id = %s AND aadhar = %s""",
        (session_id, aadhar)
    )

    if not otp_session:
        return jsonify({'success': False, 'error': 'Invalid session'}), 400

    if otp_session['is_used']:
        return jsonify({'success': False, 'error': 'OTP has already been used'}), 400

    # Check if OTP has expired
    if otp_session['expires_at'] and otp_session['expires_at'] < datetime.now():
        return jsonify({'success': False, 'error': 'OTP has expired. Please request a new one.'}), 400

    if otp_session['attempts'] >= 5:
        return jsonify({'success': False, 'error': 'Too many attempts. Request a new OTP.'}), 400

    # Increment attempts
    execute(
        "UPDATE otp_sessions SET attempts = attempts + 1 WHERE session_id = %s",
        (session_id,)
    )

    # Verify OTP hash
    if hash_otp(otp) != otp_session['otp_hash']:
        return jsonify({'success': False, 'error': 'Invalid OTP'}), 400

    # Mark session as used
    execute(
        "UPDATE otp_sessions SET is_used = TRUE WHERE session_id = %s",
        (session_id,)
    )

    # Get voter details
    voter = query_one(
        """SELECT voter_id, name, constituency_id, booth_id
           FROM voters WHERE aadhar = %s""",
        (aadhar,)
    )

    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404

    # Create Flask session
    session['voter_id'] = voter['voter_id']
    session['voter_name'] = voter['name']
    session['constituency_id'] = voter['constituency_id']
    session['booth_id'] = voter['booth_id']
    session['user_type'] = 'voter'

    return jsonify({
        'success': True,
        'voter_id': voter['voter_id'],
        'name': voter['name'],
        'message': 'Login successful'
    })


@auth_bp.route('/auth/admin-login', methods=['POST'])
def admin_login():
    """Admin login with username and password."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400

    # Look up admin
    admin = query_one(
        "SELECT admin_id, username, password_hash, name, role, constituency_id FROM admins WHERE username = %s",
        (username,)
    )

    if not admin:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    # For demo: password is the part after 'pbkdf2:sha256:'
    stored_hash = admin['password_hash']
    expected_password = stored_hash.split(':')[-1] if ':' in stored_hash else stored_hash

    if password != expected_password:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    # Update last login
    execute("UPDATE admins SET last_login = NOW() WHERE admin_id = %s", (admin['admin_id'],))

    # Create Flask session
    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_role'] = admin['role']
    session['admin_constituency'] = admin['constituency_id']
    session['user_type'] = 'admin'

    return jsonify({
        'success': True,
        'role': admin['role'],
        'name': admin['name'],
        'message': 'Admin login successful'
    })


@auth_bp.route('/auth/logout', methods=['POST'])
def logout():
    """Clear session."""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})
