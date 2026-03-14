"""Voter-facing API routes."""
from flask import Blueprint, jsonify, session
from db import query_one, query_all
from routes.auth import voter_required

voter_bp = Blueprint('voter', __name__)


@voter_bp.route('/voter/me', methods=['GET'])
@voter_required
def get_voter_profile():
    """Return voter profile from v_voter_card view."""
    voter_id = session['voter_id']
    voter = query_one("SELECT * FROM v_voter_card WHERE voter_id = %s", (voter_id,))
    if not voter:
        return jsonify({'success': False, 'error': 'Voter not found'}), 404

    # Convert date/datetime objects to strings
    if voter.get('dob'):
        voter['dob'] = str(voter['dob'])

    return jsonify({'success': True, 'voter': voter})


@voter_bp.route('/constituencies', methods=['GET'])
def get_constituencies():
    """Return all 16 constituencies."""
    constituencies = query_all(
        """SELECT constituency_id, name, type, region, total_voters, voted_count,
                  total_candidates, returning_officer,
                  ROUND((voted_count / NULLIF(total_voters, 0)) * 100, 2) AS turnout_percent
           FROM constituencies ORDER BY constituency_id"""
    )
    return jsonify({'success': True, 'constituencies': constituencies})


@voter_bp.route('/constituencies/<int:cid>/candidates', methods=['GET'])
def get_constituency_candidates(cid):
    """Return candidates for a constituency with party info."""
    candidates = query_all(
        """SELECT c.candidate_id, c.name, c.age, c.gender, c.criminal_cases,
                  c.assets_lakh, c.liabilities_lakh, c.education, c.status,
                  p.party_id, p.name AS party_name, p.abbr AS party_abbr,
                  p.color_code, p.symbol_desc
           FROM candidates c
           JOIN parties p ON c.party_id = p.party_id
           WHERE c.constituency_id = %s AND c.status = 'ACTIVE'
           ORDER BY p.party_id""",
        (cid,)
    )
    # Also fetch constituency details
    constituency = query_one(
        "SELECT * FROM constituencies WHERE constituency_id = %s", (cid,)
    )
    return jsonify({
        'success': True,
        'constituency': constituency,
        'candidates': candidates
    })


@voter_bp.route('/candidates/<int:cid>', methods=['GET'])
def get_candidate_detail(cid):
    """Return single candidate full detail."""
    candidate = query_one(
        """SELECT c.*, p.name AS party_name, p.abbr AS party_abbr,
                  p.color_code, p.symbol_desc, p.alliance,
                  co.name AS constituency_name, co.type AS constituency_type
           FROM candidates c
           JOIN parties p ON c.party_id = p.party_id
           JOIN constituencies co ON c.constituency_id = co.constituency_id
           WHERE c.candidate_id = %s""",
        (cid,)
    )
    if not candidate:
        return jsonify({'success': False, 'error': 'Candidate not found'}), 404

    if candidate.get('nomination_date'):
        candidate['nomination_date'] = str(candidate['nomination_date'])
    if candidate.get('assets_lakh'):
        candidate['assets_lakh'] = float(candidate['assets_lakh'])
    if candidate.get('liabilities_lakh'):
        candidate['liabilities_lakh'] = float(candidate['liabilities_lakh'])

    return jsonify({'success': True, 'candidate': candidate})
