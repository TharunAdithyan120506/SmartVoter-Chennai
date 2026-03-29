-- ============================================================
-- Stored Procedures for Chennai Election Portal
-- ============================================================

USE election_db;

-- -----------------------------------------------
-- Procedure 1: cast_vote (atomic vote transaction)
-- -----------------------------------------------
DROP PROCEDURE IF EXISTS cast_vote;
DELIMITER $$
CREATE PROCEDURE cast_vote(
  IN p_voter_id       VARCHAR(20),
  IN p_candidate_id   INT,
  IN p_admin_id       INT,
  OUT p_result        VARCHAR(100)
)
BEGIN
  DECLARE v_constituency_id  INT;
  DECLARE v_booth_id         INT;
  DECLARE v_cand_const       INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    SET p_result = 'ERROR: Transaction failed and was rolled back.';
  END;

  START TRANSACTION;

    -- Validate voter exists and hasn't voted
    SELECT constituency_id, booth_id INTO v_constituency_id, v_booth_id
      FROM voters WHERE voter_id = p_voter_id AND has_voted = FALSE;

    IF v_constituency_id IS NULL THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Voter not found or already voted.';
    END IF;

    -- Validate candidate is in same constituency
    SELECT constituency_id INTO v_cand_const
      FROM candidates WHERE candidate_id = p_candidate_id AND status = 'ACTIVE';

    IF v_cand_const != v_constituency_id THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Candidate not in voter constituency.';
    END IF;

    -- Insert vote record
    INSERT INTO votes (voter_id, candidate_id, constituency_id, booth_id, admin_id)
    VALUES (p_voter_id, p_candidate_id, v_constituency_id, v_booth_id, p_admin_id);

  COMMIT;
  SET p_result = 'SUCCESS: Vote recorded.';
END$$
DELIMITER ;

-- -----------------------------------------------
-- Procedure 2: verify_voter (lookup for polling mode)
-- -----------------------------------------------
DROP PROCEDURE IF EXISTS verify_voter;
DELIMITER $$
CREATE PROCEDURE verify_voter(IN p_aadhar CHAR(12))
BEGIN
  SELECT
    v.voter_id, v.name, v.age, v.gender, v.has_voted,
    v.booth_id, v.serial_no,
    c.name AS constituency_name,
    c.constituency_id,
    pb.booth_name
  FROM voters v
  JOIN constituencies c  ON v.constituency_id = c.constituency_id
  JOIN polling_booths pb ON v.booth_id = pb.booth_id
  WHERE v.aadhar = p_aadhar;
END$$
DELIMITER ;

-- -----------------------------------------------
-- Procedure 3: get_constituency_results
-- -----------------------------------------------
DROP PROCEDURE IF EXISTS get_constituency_results;
DELIMITER $$
CREATE PROCEDURE get_constituency_results(IN p_constituency_id INT)
BEGIN
  SELECT
    ca.candidate_id,
    ca.name AS candidate_name,
    ca.age,
    ca.gender,
    p.name AS party_name,
    p.abbr AS party_abbr,
    p.color_code,
    COUNT(vo.vote_id) AS vote_count,
    RANK() OVER (ORDER BY COUNT(vo.vote_id) DESC) AS position
  FROM candidates ca
  JOIN parties p ON ca.party_id = p.party_id
  LEFT JOIN votes vo ON ca.candidate_id = vo.candidate_id
  WHERE ca.constituency_id = p_constituency_id AND ca.status = 'ACTIVE'
  GROUP BY ca.candidate_id
  ORDER BY vote_count DESC;
END$$
DELIMITER ;

-- -----------------------------------------------
-- Procedure 4: generate_otp_session
-- -----------------------------------------------
DROP PROCEDURE IF EXISTS generate_otp_session;
DELIMITER $$
CREATE PROCEDURE generate_otp_session(
  IN p_aadhar    CHAR(12),
  IN p_otp_hash  VARCHAR(64),
  OUT p_session_id VARCHAR(36)
)
BEGIN
  -- Expire old sessions for this aadhar
  UPDATE otp_sessions SET is_used = TRUE
    WHERE aadhar = p_aadhar AND is_used = FALSE;

  -- Create new session
  SET p_session_id = UUID();
  INSERT INTO otp_sessions (session_id, aadhar, otp_hash, expires_at)
  VALUES (p_session_id, p_aadhar, p_otp_hash, DATE_ADD(NOW(), INTERVAL 10 MINUTE));
END$$
DELIMITER ;
