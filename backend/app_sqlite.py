#!/usr/bin/env python3
"""
Self-contained SQLite demo server for Chennai Election Portal.
This replaces MySQL with SQLite for environments where MySQL is unavailable.
All seed data is loaded on startup. The MySQL SQL files remain the production version.
"""
import csv
import hashlib
import json
import os
import random
import sqlite3
import string
import uuid
from functools import wraps

from flask import Flask, Blueprint, request, jsonify, session, g, send_from_directory
from flask_cors import CORS

# ============================================================
# Config
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'election.db')
SEED_DIR = os.path.join(PROJECT_DIR, 'database', 'seed')
FRONTEND_DIR = os.path.join(PROJECT_DIR, 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-prod'
CORS(app, supports_credentials=True)


# ============================================================
# Database Helpers
# ============================================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def query_one(sql, params=()):
    cur = get_db().execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


def query_all(sql, params=()):
    cur = get_db().execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid


# ============================================================
# Auth Decorators
# ============================================================
def voter_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'voter_id' not in session:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'success': False, 'error': 'Admin authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()


# ============================================================
# Auth Routes
# ============================================================
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    if not data or 'aadhar' not in data:
        return jsonify({'success': False, 'error': 'Aadhar number is required'}), 400

    aadhar = data['aadhar'].replace(' ', '')
    if len(aadhar) != 12 or not aadhar.isdigit():
        return jsonify({'success': False, 'error': 'Invalid Aadhar number format'}), 400

    voter = query_one("SELECT voter_id, name, phone FROM voters WHERE aadhar = ?", (aadhar,))
    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found with this Aadhar number'}), 404

    otp = ''.join(random.choices(string.digits, k=6))
    otp_hashed = hash_otp(otp)
    session_id = str(uuid.uuid4())

    # Expire old sessions
    execute("UPDATE otp_sessions SET is_used = 1 WHERE aadhar = ? AND is_used = 0", (aadhar,))

    # Create new session
    execute(
        "INSERT INTO otp_sessions (session_id, aadhar, otp_hash, expires_at) VALUES (?, ?, ?, datetime('now', '+10 minutes'))",
        (session_id, aadhar, otp_hashed)
    )

    phone = voter['phone']
    masked_phone = 'XXXXX' + phone[-5:] if len(phone) >= 5 else phone

    print(f"[MOCK OTP] Aadhar: {aadhar} → OTP: {otp}")

    return jsonify({
        'success': True,
        'session_id': session_id,
        'masked_phone': masked_phone,
        'otp': otp,
        'message': f'OTP sent to {masked_phone}'
    })


@auth_bp.route('/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    aadhar = data.get('aadhar', '').replace(' ', '')
    sid = data.get('session_id', '')
    otp = data.get('otp', '')

    if not all([aadhar, sid, otp]):
        return jsonify({'success': False, 'error': 'Aadhar, session_id, and OTP are required'}), 400

    otp_session = query_one(
        "SELECT session_id, otp_hash, is_used, attempts FROM otp_sessions WHERE session_id = ? AND aadhar = ?",
        (sid, aadhar)
    )

    if not otp_session:
        return jsonify({'success': False, 'error': 'Invalid session'}), 400
    if otp_session['is_used']:
        return jsonify({'success': False, 'error': 'OTP has already been used'}), 400
    if otp_session['attempts'] >= 5:
        return jsonify({'success': False, 'error': 'Too many attempts. Request a new OTP.'}), 400

    execute("UPDATE otp_sessions SET attempts = attempts + 1 WHERE session_id = ?", (sid,))

    if hash_otp(otp) != otp_session['otp_hash']:
        return jsonify({'success': False, 'error': 'Invalid OTP'}), 400

    execute("UPDATE otp_sessions SET is_used = 1 WHERE session_id = ?", (sid,))

    voter = query_one("SELECT voter_id, name, constituency_id, booth_id FROM voters WHERE aadhar = ?", (aadhar,))
    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404

    session['voter_id'] = voter['voter_id']
    session['voter_name'] = voter['name']
    session['constituency_id'] = voter['constituency_id']
    session['booth_id'] = voter['booth_id']
    session['user_type'] = 'voter'

    return jsonify({'success': True, 'voter_id': voter['voter_id'], 'name': voter['name'], 'message': 'Login successful'})


@auth_bp.route('/auth/admin-login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400

    admin = query_one("SELECT admin_id, username, password_hash, name, role, constituency_id FROM admins WHERE username = ?", (username,))
    if not admin:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    stored_hash = admin['password_hash']
    expected_password = stored_hash.split(':')[-1] if ':' in stored_hash else stored_hash

    if password != expected_password:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    session['admin_id'] = admin['admin_id']
    session['admin_name'] = admin['name']
    session['admin_role'] = admin['role']
    session['admin_constituency'] = admin['constituency_id']
    session['user_type'] = 'admin'

    return jsonify({'success': True, 'role': admin['role'], 'name': admin['name'], 'message': 'Admin login successful'})


@auth_bp.route('/auth/logout', methods=['POST'])
def logout_route():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


# ============================================================
# Voter Routes
# ============================================================
voter_bp = Blueprint('voter', __name__)


@voter_bp.route('/voter/me', methods=['GET'])
@voter_required
def get_voter_profile():
    voter_id = session['voter_id']
    voter = query_one("""
        SELECT v.voter_id, v.name, v.age, v.gender, v.dob, v.address, v.serial_no, v.has_voted,
               c.name AS constituency_name, c.type AS constituency_type,
               pb.booth_name, pb.address AS booth_address
        FROM voters v
        JOIN constituencies c ON v.constituency_id = c.constituency_id
        JOIN polling_booths pb ON v.booth_id = pb.booth_id
        WHERE v.voter_id = ?
    """, (voter_id,))
    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404
    return jsonify({'success': True, 'voter': voter})


@voter_bp.route('/constituencies', methods=['GET'])
def get_constituencies():
    constituencies = query_all("""
        SELECT constituency_id, name, type, region, total_voters, voted_count,
               total_candidates, returning_officer,
               ROUND(CAST(voted_count AS REAL) / NULLIF(total_voters, 0) * 100, 2) AS turnout_percent
        FROM constituencies ORDER BY constituency_id
    """)
    return jsonify({'success': True, 'constituencies': constituencies})


@voter_bp.route('/constituencies/<int:cid>/candidates', methods=['GET'])
def get_constituency_candidates(cid):
    candidates = query_all("""
        SELECT c.candidate_id, c.name, c.age, c.gender, c.criminal_cases,
               c.assets_lakh, c.liabilities_lakh, c.education, c.status,
               p.party_id, p.name AS party_name, p.abbr AS party_abbr,
               p.color_code, p.symbol_desc
        FROM candidates c JOIN parties p ON c.party_id = p.party_id
        WHERE c.constituency_id = ? AND c.status = 'ACTIVE' ORDER BY p.party_id
    """, (cid,))
    constituency = query_one("SELECT * FROM constituencies WHERE constituency_id = ?", (cid,))
    return jsonify({'success': True, 'constituency': constituency, 'candidates': candidates})


@voter_bp.route('/candidates/<int:cid>', methods=['GET'])
def get_candidate_detail(cid):
    candidate = query_one("""
        SELECT c.*, p.name AS party_name, p.abbr AS party_abbr,
               p.color_code, p.symbol_desc, p.alliance,
               co.name AS constituency_name, co.type AS constituency_type
        FROM candidates c
        JOIN parties p ON c.party_id = p.party_id
        JOIN constituencies co ON c.constituency_id = co.constituency_id
        WHERE c.candidate_id = ?
    """, (cid,))
    if not candidate:
        return jsonify({'success': False, 'error': 'Candidate not found'}), 404
    return jsonify({'success': True, 'candidate': candidate})


# ============================================================
# Admin Routes
# ============================================================
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def get_dashboard():
    turnout = query_all("""
        SELECT constituency_id, name, type, region, total_voters, voted_count,
               ROUND(CAST(voted_count AS REAL) / NULLIF(total_voters, 0) * 100, 2) AS turnout_percent
        FROM constituencies ORDER BY turnout_percent DESC
    """)
    total_voters = sum(r['total_voters'] or 0 for r in turnout)
    total_voted = sum(r['voted_count'] or 0 for r in turnout)
    overall_pct = round((total_voted / total_voters * 100), 2) if total_voters > 0 else 0
    total_candidates = query_one("SELECT COUNT(*) AS cnt FROM candidates WHERE status = 'ACTIVE'")
    total_booths = query_one("SELECT COUNT(*) AS cnt FROM polling_booths")

    return jsonify({
        'success': True,
        'summary': {
            'total_voters': total_voters,
            'total_voted': total_voted,
            'overall_turnout': overall_pct,
            'total_constituencies': len(turnout),
            'total_candidates': total_candidates['cnt'] if total_candidates else 0,
            'total_booths': total_booths['cnt'] if total_booths else 0,
        },
        'turnout': turnout
    })


@admin_bp.route('/voters', methods=['GET'])
@admin_required
def get_voters():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    search = request.args.get('search', '').strip()
    offset = (page - 1) * limit

    if search:
        sl = f'%{search}%'
        voters = query_all("""
            SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.phone, v.address, v.has_voted, v.serial_no,
                   c.name AS constituency_name, v.constituency_id, pb.booth_name, v.booth_id
            FROM voters v JOIN constituencies c ON v.constituency_id = c.constituency_id
            JOIN polling_booths pb ON v.booth_id = pb.booth_id
            WHERE v.name LIKE ? OR v.voter_id LIKE ? OR v.aadhar LIKE ?
            ORDER BY v.voter_id LIMIT ? OFFSET ?
        """, (sl, sl, sl, limit, offset))
        total = query_one("SELECT COUNT(*) AS cnt FROM voters WHERE name LIKE ? OR voter_id LIKE ? OR aadhar LIKE ?", (sl, sl, sl))
    else:
        voters = query_all("""
            SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.phone, v.address, v.has_voted, v.serial_no,
                   c.name AS constituency_name, v.constituency_id, pb.booth_name, v.booth_id
            FROM voters v JOIN constituencies c ON v.constituency_id = c.constituency_id
            JOIN polling_booths pb ON v.booth_id = pb.booth_id
            ORDER BY v.voter_id LIMIT ? OFFSET ?
        """, (limit, offset))
        total = query_one("SELECT COUNT(*) AS cnt FROM voters")

    cnt = total['cnt'] if total else 0
    return jsonify({
        'success': True, 'voters': voters, 'total': cnt,
        'page': page, 'limit': limit, 'pages': (cnt + limit - 1) // limit if cnt else 0
    })


@admin_bp.route('/voters/<path:voter_id>', methods=['PUT'])
@admin_required
def update_voter(voter_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    allowed = ['name', 'phone', 'address']
    updates, values = [], []
    for f in allowed:
        if f in data:
            updates.append(f"{f} = ?")
            values.append(data[f])
    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

    values.append(voter_id)
    execute(f"UPDATE voters SET {', '.join(updates)} WHERE voter_id = ?", values)
    return jsonify({'success': True, 'message': 'Voter updated successfully'})


@admin_bp.route('/candidates', methods=['GET'])
@admin_required
def get_candidates():
    cid = request.args.get('constituency_id', type=int)
    if cid:
        candidates = query_all("""
            SELECT c.*, p.name AS party_name, p.abbr AS party_abbr, p.color_code, co.name AS constituency_name
            FROM candidates c JOIN parties p ON c.party_id = p.party_id
            JOIN constituencies co ON c.constituency_id = co.constituency_id
            WHERE c.constituency_id = ? ORDER BY c.candidate_id
        """, (cid,))
    else:
        candidates = query_all("""
            SELECT c.*, p.name AS party_name, p.abbr AS party_abbr, p.color_code, co.name AS constituency_name
            FROM candidates c JOIN parties p ON c.party_id = p.party_id
            JOIN constituencies co ON c.constituency_id = co.constituency_id
            ORDER BY c.constituency_id, c.candidate_id
        """)
    return jsonify({'success': True, 'candidates': candidates})


@admin_bp.route('/polling/verify', methods=['POST'])
@admin_required
def polling_verify():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    voter_id = data.get('voter_id', '').strip()
    aadhar = data.get('aadhar', '').strip()

    if voter_id:
        voter = query_one("""
            SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.has_voted,
                   v.booth_id, v.serial_no, v.constituency_id,
                   c.name AS constituency_name, pb.booth_name
            FROM voters v JOIN constituencies c ON v.constituency_id = c.constituency_id
            JOIN polling_booths pb ON v.booth_id = pb.booth_id
            WHERE v.voter_id = ?
        """, (voter_id,))
    elif aadhar:
        voter = query_one("""
            SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.has_voted,
                   v.booth_id, v.serial_no, v.constituency_id,
                   c.name AS constituency_name, pb.booth_name
            FROM voters v JOIN constituencies c ON v.constituency_id = c.constituency_id
            JOIN polling_booths pb ON v.booth_id = pb.booth_id
            WHERE v.aadhar = ?
        """, (aadhar,))
    else:
        return jsonify({'success': False, 'error': 'voter_id or aadhar is required'}), 400

    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404
    if voter['has_voted']:
        return jsonify({'success': False, 'error': 'Voter has already cast their vote'}), 400

    candidates = query_all("""
        SELECT c.candidate_id, c.name, c.age, c.gender,
               p.party_id, p.name AS party_name, p.abbr AS party_abbr, p.color_code, p.symbol_desc
        FROM candidates c JOIN parties p ON c.party_id = p.party_id
        WHERE c.constituency_id = ? AND c.status = 'ACTIVE' ORDER BY c.candidate_id
    """, (voter['constituency_id'],))

    return jsonify({'success': True, 'voter': voter, 'candidates': candidates})


@admin_bp.route('/polling/vote', methods=['POST'])
@admin_required
def polling_vote():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    voter_id = data.get('voter_id', '').strip()
    candidate_id = data.get('candidate_id')
    admin_id = session.get('admin_id')

    if not voter_id or not candidate_id:
        return jsonify({'success': False, 'error': 'voter_id and candidate_id are required'}), 400

    # Check voter
    voter = query_one("SELECT constituency_id, booth_id, has_voted FROM voters WHERE voter_id = ?", (voter_id,))
    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404
    if voter['has_voted']:
        return jsonify({'success': False, 'error': 'Voter has already cast their vote'}), 400

    # Check candidate same constituency
    cand = query_one("SELECT constituency_id FROM candidates WHERE candidate_id = ? AND status = 'ACTIVE'", (int(candidate_id),))
    if not cand:
        return jsonify({'success': False, 'error': 'Candidate not found'}), 404
    if cand['constituency_id'] != voter['constituency_id']:
        return jsonify({'success': False, 'error': 'Candidate not in voter constituency'}), 400

    db = get_db()
    try:
        db.execute("INSERT INTO votes (voter_id, candidate_id, constituency_id, booth_id, admin_id) VALUES (?, ?, ?, ?, ?)",
                   (voter_id, int(candidate_id), voter['constituency_id'], voter['booth_id'], admin_id))
        db.execute("UPDATE voters SET has_voted = 1 WHERE voter_id = ?", (voter_id,))
        db.execute("UPDATE constituencies SET voted_count = voted_count + 1 WHERE constituency_id = ?", (voter['constituency_id'],))
        db.commit()
        return jsonify({'success': True, 'message': 'Vote recorded successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/results', methods=['GET'])
@admin_required
def get_results():
    # Get leading candidate per constituency
    results = query_all("""
        SELECT ca.candidate_id, ca.name AS candidate_name, ca.age, ca.criminal_cases, ca.assets_lakh,
               p.name AS party_name, p.abbr AS party_abbr, p.color_code,
               co.name AS constituency_name, co.constituency_id,
               COUNT(v.vote_id) AS vote_count
        FROM candidates ca
        JOIN parties p ON ca.party_id = p.party_id
        JOIN constituencies co ON ca.constituency_id = co.constituency_id
        LEFT JOIN votes v ON ca.candidate_id = v.candidate_id
        WHERE ca.status = 'ACTIVE'
        GROUP BY ca.candidate_id
        HAVING vote_count > 0
        ORDER BY co.constituency_id, vote_count DESC
    """)

    # Keep only top per constituency
    seen = set()
    leaders = []
    for r in results:
        cid = r['constituency_id']
        if cid not in seen:
            seen.add(cid)
            leaders.append(r)

    return jsonify({'success': True, 'results': leaders})


@admin_bp.route('/results/<int:constituency_id>', methods=['GET'])
@admin_required
def get_constituency_results(constituency_id):
    results = query_all("""
        SELECT ca.candidate_id, ca.name AS candidate_name, ca.age, ca.gender,
               p.name AS party_name, p.abbr AS party_abbr, p.color_code,
               COUNT(v.vote_id) AS vote_count
        FROM candidates ca
        JOIN parties p ON ca.party_id = p.party_id
        LEFT JOIN votes v ON ca.candidate_id = v.candidate_id
        WHERE ca.constituency_id = ? AND ca.status = 'ACTIVE'
        GROUP BY ca.candidate_id
        ORDER BY vote_count DESC
    """, (constituency_id,))

    # Add position
    for i, r in enumerate(results):
        r['position'] = i + 1

    return jsonify({'success': True, 'results': results})


# ============================================================
# Static Routes
# ============================================================
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)


# ============================================================
# Register Blueprints
# ============================================================
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(voter_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api/admin')


# ============================================================
# Database Initialization
# ============================================================
def init_db():
    """Create tables and load seed data from CSVs."""
    if os.path.exists(DB_PATH):
        print("Database already exists. Delete election.db to re-seed.")
        return

    print("Initializing SQLite database...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create tables
    c.executescript("""
        CREATE TABLE IF NOT EXISTS parties (
            party_id TEXT PRIMARY KEY, name TEXT NOT NULL, abbr TEXT NOT NULL,
            color_code TEXT DEFAULT '#888888', alliance TEXT, founded_year INTEGER, symbol_desc TEXT
        );
        CREATE TABLE IF NOT EXISTS constituencies (
            constituency_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL DEFAULT 'GENERAL', region TEXT NOT NULL,
            total_voters INTEGER DEFAULT 0, voted_count INTEGER DEFAULT 0,
            total_candidates INTEGER DEFAULT 0, returning_officer TEXT
        );
        CREATE TABLE IF NOT EXISTS polling_booths (
            booth_id INTEGER PRIMARY KEY, booth_name TEXT NOT NULL,
            constituency_id INTEGER NOT NULL, address TEXT, total_voters INTEGER DEFAULT 0,
            booth_officer TEXT, FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
        );
        CREATE TABLE IF NOT EXISTS voters (
            voter_id TEXT PRIMARY KEY, aadhar TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            age INTEGER NOT NULL, gender TEXT NOT NULL, dob TEXT NOT NULL,
            address TEXT NOT NULL, phone TEXT NOT NULL, constituency_id INTEGER NOT NULL,
            booth_id INTEGER NOT NULL, serial_no INTEGER NOT NULL, has_voted INTEGER DEFAULT 0,
            photo_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id),
            FOREIGN KEY (booth_id) REFERENCES polling_booths(booth_id)
        );
        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL,
            gender TEXT NOT NULL, party_id TEXT NOT NULL, constituency_id INTEGER NOT NULL,
            criminal_cases INTEGER DEFAULT 0, assets_lakh REAL DEFAULT 0,
            liabilities_lakh REAL DEFAULT 0, education TEXT,
            status TEXT DEFAULT 'ACTIVE', nomination_date TEXT, photo_path TEXT,
            FOREIGN KEY (party_id) REFERENCES parties(party_id),
            FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
        );
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'BOOTH_ADMIN', constituency_id INTEGER,
            last_login TEXT, FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
        );
        CREATE TABLE IF NOT EXISTS votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT, voter_id TEXT NOT NULL UNIQUE,
            candidate_id INTEGER NOT NULL, constituency_id INTEGER NOT NULL,
            booth_id INTEGER NOT NULL, admin_id INTEGER NOT NULL,
            voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (voter_id) REFERENCES voters(voter_id),
            FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id),
            FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id),
            FOREIGN KEY (booth_id) REFERENCES polling_booths(booth_id),
            FOREIGN KEY (admin_id) REFERENCES admins(admin_id)
        );
        CREATE TABLE IF NOT EXISTS otp_sessions (
            session_id TEXT PRIMARY KEY, aadhar TEXT NOT NULL, otp_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
            entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
            old_value TEXT, new_value TEXT, admin_id INTEGER NOT NULL,
            performed_at TEXT DEFAULT CURRENT_TIMESTAMP, ip_address TEXT,
            FOREIGN KEY (admin_id) REFERENCES admins(admin_id)
        );
        CREATE TABLE IF NOT EXISTS election_config (
            config_key TEXT PRIMARY KEY, config_value TEXT NOT NULL,
            description TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER, FOREIGN KEY (updated_by) REFERENCES admins(admin_id)
        );

        CREATE INDEX IF NOT EXISTS idx_voters_aadhar ON voters(aadhar);
        CREATE INDEX IF NOT EXISTS idx_votes_constituency ON votes(constituency_id);
        CREATE INDEX IF NOT EXISTS idx_candidates_constituency ON candidates(constituency_id);
    """)

    # Load CSVs
    csv_tables = [
        ('parties', 'parties.csv', ['party_id', 'name', 'abbr', 'color_code', 'alliance', 'founded_year', 'symbol_desc']),
        ('constituencies', 'constituencies.csv', ['constituency_id', 'name', 'type', 'region', 'total_voters', 'voted_count', 'returning_officer']),
        ('polling_booths', 'polling_booths.csv', ['booth_id', 'booth_name', 'constituency_id', 'address', 'total_voters', 'booth_officer']),
        ('voters', 'voters.csv', ['voter_id', 'aadhar', 'name', 'age', 'gender', 'dob', 'address', 'phone', 'constituency_id', 'booth_id', 'serial_no', 'has_voted']),
        ('candidates', 'candidates.csv', ['candidate_id', 'name', 'age', 'gender', 'party_id', 'constituency_id', 'criminal_cases', 'assets_lakh', 'liabilities_lakh', 'education', 'status', 'nomination_date']),
        ('admins', 'admins.csv', ['admin_id', 'username', 'password_hash', 'name', 'role', 'constituency_id']),
    ]

    for table, fname, cols in csv_tables:
        fpath = os.path.join(SEED_DIR, fname)
        with open(fpath, 'r') as f:
            reader = csv.DictReader(f)
            placeholders = ', '.join(['?'] * len(cols))
            colnames = ', '.join(cols)
            count = 0
            for row in reader:
                values = []
                for col in cols:
                    val = row.get(col, '').strip()
                    if val == '' or val == 'NULL':
                        values.append(None)
                    elif val == 'FALSE':
                        values.append(0)
                    elif val == 'TRUE':
                        values.append(1)
                    else:
                        values.append(val)
                c.execute(f"INSERT INTO {table} ({colnames}) VALUES ({placeholders})", values)
                count += 1
            print(f"  ✓ {table}: {count} rows")

    # Election config
    c.execute("INSERT INTO election_config (config_key, config_value, description) VALUES ('election_phase', 'POLLING', 'Current election phase')")
    c.execute("INSERT INTO election_config (config_key, config_value, description) VALUES ('election_date', '2026-04-15', 'Date of the election')")
    c.execute("INSERT INTO election_config (config_key, config_value, description) VALUES ('results_declared', 'FALSE', 'Whether results declared')")

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    init_db()
    print("\n🗳️  Chennai Election Portal running at http://localhost:5000\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
