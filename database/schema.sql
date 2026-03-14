-- ============================================================
-- Chennai District Election Management Portal
-- Database Schema — 10 Tables
-- ============================================================

DROP DATABASE IF EXISTS election_db;
CREATE DATABASE election_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE election_db;

-- -----------------------------------------------
-- Table 1: parties
-- -----------------------------------------------
CREATE TABLE parties (
  party_id    VARCHAR(10)  PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  abbr        VARCHAR(10)  NOT NULL,
  color_code  VARCHAR(7)   DEFAULT '#888888',
  alliance    VARCHAR(50),
  founded_year INT,
  symbol_desc VARCHAR(100)
);

-- -----------------------------------------------
-- Table 2: constituencies
-- -----------------------------------------------
CREATE TABLE constituencies (
  constituency_id   INT          PRIMARY KEY AUTO_INCREMENT,
  name              VARCHAR(100) NOT NULL UNIQUE,
  type              ENUM('GENERAL','SC') NOT NULL DEFAULT 'GENERAL',
  region            ENUM('North','Central','South') NOT NULL,
  total_voters      INT          DEFAULT 0,
  voted_count       INT          DEFAULT 0,
  total_candidates  INT          DEFAULT 0,
  returning_officer VARCHAR(100),
  CONSTRAINT chk_voted CHECK (voted_count <= total_voters)
);

-- -----------------------------------------------
-- Table 3: polling_booths
-- -----------------------------------------------
CREATE TABLE polling_booths (
  booth_id         INT          PRIMARY KEY AUTO_INCREMENT,
  booth_name       VARCHAR(100) NOT NULL,
  constituency_id  INT          NOT NULL,
  address          VARCHAR(200),
  total_voters     INT          DEFAULT 0,
  booth_officer    VARCHAR(100),
  FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- -----------------------------------------------
-- Table 4: voters
-- -----------------------------------------------
CREATE TABLE voters (
  voter_id         VARCHAR(20)  PRIMARY KEY,
  aadhar           CHAR(12)     NOT NULL UNIQUE,
  name             VARCHAR(100) NOT NULL,
  age              INT          NOT NULL,
  gender           ENUM('Male','Female','Other') NOT NULL,
  dob              DATE         NOT NULL,
  address          VARCHAR(250) NOT NULL,
  phone            VARCHAR(10)  NOT NULL,
  constituency_id  INT          NOT NULL,
  booth_id         INT          NOT NULL,
  serial_no        INT          NOT NULL,
  has_voted        BOOLEAN      DEFAULT FALSE,
  photo_path       VARCHAR(200) DEFAULT NULL,
  created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_voter_age CHECK (age >= 18),
  FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (booth_id) REFERENCES polling_booths(booth_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- -----------------------------------------------
-- Table 5: candidates
-- -----------------------------------------------
CREATE TABLE candidates (
  candidate_id     INT          PRIMARY KEY AUTO_INCREMENT,
  name             VARCHAR(100) NOT NULL,
  age              INT          NOT NULL,
  gender           ENUM('Male','Female','Other') NOT NULL,
  party_id         VARCHAR(10)  NOT NULL,
  constituency_id  INT          NOT NULL,
  criminal_cases   INT          DEFAULT 0,
  assets_lakh      DECIMAL(10,2) DEFAULT 0,
  liabilities_lakh DECIMAL(10,2) DEFAULT 0,
  education        VARCHAR(100),
  status           ENUM('ACTIVE','WITHDRAWN','DISQUALIFIED') DEFAULT 'ACTIVE',
  nomination_date  DATE,
  photo_path       VARCHAR(200) DEFAULT NULL,
  CONSTRAINT chk_cand_age CHECK (age >= 25),
  FOREIGN KEY (party_id) REFERENCES parties(party_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- -----------------------------------------------
-- Table 6: admins
-- -----------------------------------------------
CREATE TABLE admins (
  admin_id      INT          PRIMARY KEY AUTO_INCREMENT,
  username      VARCHAR(50)  NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  name          VARCHAR(100) NOT NULL,
  role          ENUM('SUPER_ADMIN','BOOTH_ADMIN') NOT NULL DEFAULT 'BOOTH_ADMIN',
  constituency_id INT        DEFAULT NULL,
  last_login    TIMESTAMP    DEFAULT NULL,
  FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
    ON DELETE SET NULL
);

-- -----------------------------------------------
-- Table 7: votes (append-only)
-- -----------------------------------------------
CREATE TABLE votes (
  vote_id          BIGINT       PRIMARY KEY AUTO_INCREMENT,
  voter_id         VARCHAR(20)  NOT NULL,
  candidate_id     INT          NOT NULL,
  constituency_id  INT          NOT NULL,
  booth_id         INT          NOT NULL,
  admin_id         INT          NOT NULL,
  voted_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_one_vote_per_voter UNIQUE (voter_id),
  FOREIGN KEY (voter_id)        REFERENCES voters(voter_id) ON DELETE RESTRICT,
  FOREIGN KEY (candidate_id)    REFERENCES candidates(candidate_id) ON DELETE RESTRICT,
  FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id) ON DELETE RESTRICT,
  FOREIGN KEY (booth_id)        REFERENCES polling_booths(booth_id) ON DELETE RESTRICT,
  FOREIGN KEY (admin_id)        REFERENCES admins(admin_id) ON DELETE RESTRICT
);

-- -----------------------------------------------
-- Table 8: otp_sessions
-- -----------------------------------------------
CREATE TABLE otp_sessions (
  session_id   VARCHAR(36)  PRIMARY KEY,
  aadhar       CHAR(12)     NOT NULL,
  otp_hash     VARCHAR(64)  NOT NULL,
  created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  expires_at   TIMESTAMP    NOT NULL,
  is_used      BOOLEAN      DEFAULT FALSE,
  attempts     INT          DEFAULT 0,
  CONSTRAINT chk_attempts CHECK (attempts <= 5)
);

-- -----------------------------------------------
-- Table 9: audit_log
-- -----------------------------------------------
CREATE TABLE audit_log (
  log_id       BIGINT       PRIMARY KEY AUTO_INCREMENT,
  action       VARCHAR(50)  NOT NULL,
  entity_type  VARCHAR(50)  NOT NULL,
  entity_id    VARCHAR(50)  NOT NULL,
  old_value    JSON         DEFAULT NULL,
  new_value    JSON         DEFAULT NULL,
  admin_id     INT          NOT NULL,
  performed_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  ip_address   VARCHAR(45)  DEFAULT NULL,
  FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE RESTRICT
);

-- -----------------------------------------------
-- Table 10: election_config
-- -----------------------------------------------
CREATE TABLE election_config (
  config_key    VARCHAR(50)  PRIMARY KEY,
  config_value  VARCHAR(255) NOT NULL,
  description   VARCHAR(200),
  updated_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_by    INT,
  FOREIGN KEY (updated_by) REFERENCES admins(admin_id) ON DELETE SET NULL
);
