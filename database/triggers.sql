-- ============================================================
-- Triggers for Chennai Election Portal
-- ============================================================

USE election_db;

-- -----------------------------------------------
-- Trigger 1: Prevent double voting (BEFORE INSERT on votes)
-- -----------------------------------------------
DELIMITER $$
CREATE TRIGGER before_vote_insert
BEFORE INSERT ON votes
FOR EACH ROW
BEGIN
  DECLARE already_voted BOOLEAN;
  SELECT has_voted INTO already_voted FROM voters WHERE voter_id = NEW.voter_id;
  IF already_voted = TRUE THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'ERROR: Voter has already cast their vote.';
  END IF;
END$$
DELIMITER ;

-- -----------------------------------------------
-- Trigger 2: Mark voter as voted (AFTER INSERT on votes)
-- -----------------------------------------------
DELIMITER $$
CREATE TRIGGER after_vote_insert
AFTER INSERT ON votes
FOR EACH ROW
BEGIN
  UPDATE voters
    SET has_voted = TRUE
    WHERE voter_id = NEW.voter_id;
END$$
DELIMITER ;

-- -----------------------------------------------
-- Trigger 3: Update constituency turnout count (AFTER INSERT on votes)
-- -----------------------------------------------
DELIMITER $$
CREATE TRIGGER after_vote_update_turnout
AFTER INSERT ON votes
FOR EACH ROW
BEGIN
  UPDATE constituencies
    SET voted_count = voted_count + 1
    WHERE constituency_id = NEW.constituency_id;
END$$
DELIMITER ;

-- -----------------------------------------------
-- Trigger 4: Log admin edits to voters table (AFTER UPDATE on voters)
-- -----------------------------------------------
DELIMITER $$
CREATE TRIGGER after_voter_update_audit
AFTER UPDATE ON voters
FOR EACH ROW
BEGIN
  INSERT INTO audit_log (action, entity_type, entity_id, old_value, new_value, admin_id)
  VALUES (
    'UPDATE',
    'voters',
    OLD.voter_id,
    JSON_OBJECT('name', OLD.name, 'phone', OLD.phone, 'address', OLD.address),
    JSON_OBJECT('name', NEW.name, 'phone', NEW.phone, 'address', NEW.address),
    1
  );
END$$
DELIMITER ;
