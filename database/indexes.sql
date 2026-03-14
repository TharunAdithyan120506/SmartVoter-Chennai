-- ============================================================
-- Indexes for Chennai Election Portal
-- ============================================================

USE election_db;

-- Speed up OTP login aadhar lookup
CREATE INDEX idx_voters_aadhar ON voters(aadhar);

-- Speed up vote aggregation by constituency
CREATE INDEX idx_votes_constituency ON votes(constituency_id);

-- Speed up candidate listing per constituency
CREATE INDEX idx_candidates_constituency ON candidates(constituency_id);

-- Speed up OTP session expiry cleanup
CREATE INDEX idx_otp_expiry ON otp_sessions(expires_at, is_used);

-- Speed up audit log queries by admin
CREATE INDEX idx_audit_admin ON audit_log(admin_id, performed_at);
