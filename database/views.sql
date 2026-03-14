-- ============================================================
-- Views for Chennai Election Portal
-- ============================================================

USE election_db;

-- View 1: Turnout summary per constituency
CREATE OR REPLACE VIEW v_turnout_summary AS
SELECT
  c.constituency_id,
  c.name,
  c.type,
  c.region,
  c.total_voters,
  c.voted_count,
  ROUND((c.voted_count / NULLIF(c.total_voters, 0)) * 100, 2) AS turnout_percent
FROM constituencies c
ORDER BY turnout_percent DESC;

-- View 2: Candidate results with vote counts
CREATE OR REPLACE VIEW v_candidate_results AS
SELECT
  ca.candidate_id,
  ca.name AS candidate_name,
  ca.age,
  ca.criminal_cases,
  ca.assets_lakh,
  p.name AS party_name,
  p.abbr AS party_abbr,
  p.color_code,
  co.name AS constituency_name,
  co.constituency_id,
  COUNT(v.vote_id) AS vote_count,
  RANK() OVER (PARTITION BY ca.constituency_id ORDER BY COUNT(v.vote_id) DESC) AS rank_in_constituency
FROM candidates ca
JOIN parties p      ON ca.party_id = p.party_id
JOIN constituencies co ON ca.constituency_id = co.constituency_id
LEFT JOIN votes v   ON ca.candidate_id = v.candidate_id
WHERE ca.status = 'ACTIVE'
GROUP BY ca.candidate_id;

-- View 3: Voter card details (joined view for e-voter card rendering)
CREATE OR REPLACE VIEW v_voter_card AS
SELECT
  v.voter_id,
  v.name,
  v.age,
  v.gender,
  v.dob,
  v.address,
  v.serial_no,
  v.has_voted,
  c.name  AS constituency_name,
  c.type  AS constituency_type,
  pb.booth_name,
  pb.address AS booth_address
FROM voters v
JOIN constituencies c  ON v.constituency_id = c.constituency_id
JOIN polling_booths pb ON v.booth_id = pb.booth_id;

-- View 4: Leading candidate per constituency (for results map)
CREATE OR REPLACE VIEW v_leading_candidates AS
SELECT *
FROM v_candidate_results
WHERE rank_in_constituency = 1;
