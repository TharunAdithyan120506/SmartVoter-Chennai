"""Admin-facing API routes."""
from decimal import Decimal
from datetime import date, datetime

from flask import Blueprint, request, jsonify, session
from db import query_one, query_all, execute, call_procedure, get_db
from routes.auth import admin_required

admin_bp = Blueprint('admin', __name__)


def serialize(obj):
    """Convert non-serializable types for JSON."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return str(obj)
    return obj


def serialize_rows(rows):
    """Serialize all rows."""
    return [{k: serialize(v) for k, v in row.items()} for row in rows]


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def get_dashboard():
    """Return turnout stats from v_turnout_summary view."""
    turnout = query_all("SELECT * FROM v_turnout_summary")
    turnout = serialize_rows(turnout)

    # Summary stats
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
    """Return paginated voter list."""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    search = request.args.get('search', '').strip()

    offset = (page - 1) * limit

    if search:
        search_like = f'%{search}%'
        voters = query_all(
            """SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.phone,
                      v.address, v.has_voted, v.serial_no,
                      c.name AS constituency_name, v.constituency_id,
                      pb.booth_name, v.booth_id
               FROM voters v
               JOIN constituencies c ON v.constituency_id = c.constituency_id
               JOIN polling_booths pb ON v.booth_id = pb.booth_id
               WHERE v.name LIKE %s OR v.voter_id LIKE %s OR v.aadhar LIKE %s
               ORDER BY v.voter_id
               LIMIT %s OFFSET %s""",
            (search_like, search_like, search_like, limit, offset)
        )
        total = query_one(
            """SELECT COUNT(*) AS cnt FROM voters
               WHERE name LIKE %s OR voter_id LIKE %s OR aadhar LIKE %s""",
            (search_like, search_like, search_like)
        )
    else:
        voters = query_all(
            """SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.phone,
                      v.address, v.has_voted, v.serial_no,
                      c.name AS constituency_name, v.constituency_id,
                      pb.booth_name, v.booth_id
               FROM voters v
               JOIN constituencies c ON v.constituency_id = c.constituency_id
               JOIN polling_booths pb ON v.booth_id = pb.booth_id
               ORDER BY v.voter_id
               LIMIT %s OFFSET %s""",
            (limit, offset)
        )
        total = query_one("SELECT COUNT(*) AS cnt FROM voters")

    return jsonify({
        'success': True,
        'voters': serialize_rows(voters),
        'total': total['cnt'] if total else 0,
        'page': page,
        'limit': limit,
        'pages': (total['cnt'] + limit - 1) // limit if total else 0
    })


@admin_bp.route('/voters/<voter_id>', methods=['PUT'])
@admin_required
def update_voter(voter_id):
    """Update voter name/phone/address. Trigger auto-logs change."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    # Only allow updating name, phone, address
    allowed_fields = ['name', 'phone', 'address']
    updates = []
    values = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = %s")
            values.append(data[field])

    if not updates:
        return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

    values.append(voter_id)
    sql = f"UPDATE voters SET {', '.join(updates)} WHERE voter_id = %s"

    try:
        execute(sql, values)
        return jsonify({'success': True, 'message': 'Voter updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/candidates', methods=['GET'])
@admin_required
def get_candidates():
    """Return all candidates, filterable by constituency_id."""
    constituency_id = request.args.get('constituency_id', type=int)

    if constituency_id:
        candidates = query_all(
            """SELECT c.*, p.name AS party_name, p.abbr AS party_abbr,
                      p.color_code, co.name AS constituency_name
               FROM candidates c
               JOIN parties p ON c.party_id = p.party_id
               JOIN constituencies co ON c.constituency_id = co.constituency_id
               WHERE c.constituency_id = %s
               ORDER BY c.candidate_id""",
            (constituency_id,)
        )
    else:
        candidates = query_all(
            """SELECT c.*, p.name AS party_name, p.abbr AS party_abbr,
                      p.color_code, co.name AS constituency_name
               FROM candidates c
               JOIN parties p ON c.party_id = p.party_id
               JOIN constituencies co ON c.constituency_id = co.constituency_id
               ORDER BY c.constituency_id, c.candidate_id"""
        )

    return jsonify({
        'success': True,
        'candidates': serialize_rows(candidates)
    })


@admin_bp.route('/polling/verify', methods=['POST'])
@admin_required
def polling_verify():
    """Verify voter for polling. Accept voter_id or aadhar."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    voter_id = data.get('voter_id', '').strip()
    aadhar = data.get('aadhar', '').strip()

    if voter_id:
        voter = query_one(
            """SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.has_voted,
                      v.booth_id, v.serial_no, v.constituency_id,
                      c.name AS constituency_name,
                      pb.booth_name
               FROM voters v
               JOIN constituencies c ON v.constituency_id = c.constituency_id
               JOIN polling_booths pb ON v.booth_id = pb.booth_id
               WHERE v.voter_id = %s""",
            (voter_id,)
        )
    elif aadhar:
        voter = query_one(
            """SELECT v.voter_id, v.aadhar, v.name, v.age, v.gender, v.has_voted,
                      v.booth_id, v.serial_no, v.constituency_id,
                      c.name AS constituency_name,
                      pb.booth_name
               FROM voters v
               JOIN constituencies c ON v.constituency_id = c.constituency_id
               JOIN polling_booths pb ON v.booth_id = pb.booth_id
               WHERE v.aadhar = %s""",
            (aadhar,)
        )
    else:
        return jsonify({'success': False, 'error': 'voter_id or aadhar is required'}), 400

    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404

    if voter['has_voted']:
        return jsonify({'success': False, 'error': 'Voter has already cast their vote'}), 400

    # Get candidates for voter's constituency
    candidates = query_all(
        """SELECT c.candidate_id, c.name, c.age, c.gender,
                  p.party_id, p.name AS party_name, p.abbr AS party_abbr,
                  p.color_code, p.symbol_desc
           FROM candidates c
           JOIN parties p ON c.party_id = p.party_id
           WHERE c.constituency_id = %s AND c.status = 'ACTIVE'
           ORDER BY c.candidate_id""",
        (voter['constituency_id'],)
    )

    return jsonify({
        'success': True,
        'voter': serialize_rows([voter])[0],
        'candidates': serialize_rows(candidates)
    })


@admin_bp.route('/polling/vote', methods=['POST'])
@admin_required
def polling_vote():
    """Cast a vote — direct SQL to avoid stored procedure transaction conflicts."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    voter_id = data.get('voter_id', '').strip()
    candidate_id = data.get('candidate_id')
    admin_id = session.get('admin_id')

    if not voter_id or not candidate_id:
        return jsonify({'success': False, 'error': 'voter_id and candidate_id are required'}), 400

    try:
        db = get_db()

        # Temporarily disable autocommit for an atomic transaction
        db.autocommit = False
        cursor = db.cursor(dictionary=True)

        try:
            # 1. Validate voter exists and hasn't voted
            cursor.execute(
                "SELECT constituency_id, booth_id, has_voted FROM voters WHERE voter_id = %s FOR UPDATE",
                (voter_id,)
            )
            voter = cursor.fetchone()

            if not voter:
                db.rollback()
                return jsonify({'success': False, 'error': 'Voter not found'}), 404

            if voter['has_voted']:
                db.rollback()
                return jsonify({'success': False, 'error': 'Voter has already cast their vote'}), 400

            v_constituency_id = voter['constituency_id']
            v_booth_id = voter['booth_id']

            # 2. Validate candidate is in the same constituency
            cursor.execute(
                "SELECT constituency_id FROM candidates WHERE candidate_id = %s AND status = 'ACTIVE'",
                (int(candidate_id),)
            )
            cand = cursor.fetchone()

            if not cand:
                db.rollback()
                return jsonify({'success': False, 'error': 'Candidate not found or not active'}), 400

            if cand['constituency_id'] != v_constituency_id:
                db.rollback()
                return jsonify({'success': False, 'error': 'Candidate not in voter constituency'}), 400

            # 3. Insert vote record (triggers handle has_voted + turnout count)
            cursor.execute(
                """INSERT INTO votes (voter_id, candidate_id, constituency_id, booth_id, admin_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                (voter_id, int(candidate_id), v_constituency_id, v_booth_id, int(admin_id))
            )

            db.commit()
            cursor.close()
            db.autocommit = True

            return jsonify({'success': True, 'message': 'Vote recorded successfully'})

        except Exception as inner_e:
            db.rollback()
            db.autocommit = True
            cursor.close()
            raise inner_e

    except Exception as e:
        error_msg = str(e)
        print(f"[VOTE ERROR] {error_msg}")
        if 'already' in error_msg.lower() or 'Duplicate' in error_msg:
            return jsonify({'success': False, 'error': 'Voter has already cast their vote'}), 400
        return jsonify({'success': False, 'error': f'An error occurred while casting vote: {error_msg}'}), 500


@admin_bp.route('/results', methods=['GET'])
@admin_required
def get_results():
    """Return leading candidates from v_leading_candidates view."""
    results = query_all("SELECT * FROM v_leading_candidates")
    return jsonify({
        'success': True,
        'results': serialize_rows(results)
    })


@admin_bp.route('/results/<int:constituency_id>', methods=['GET'])
@admin_required
def get_constituency_results(constituency_id):
    """Call get_constituency_results stored procedure."""
    try:
        results = call_procedure('get_constituency_results', (constituency_id,))
        if results and len(results) > 0:
            return jsonify({
                'success': True,
                'results': serialize_rows(results[0])
            })
        return jsonify({'success': True, 'results': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
