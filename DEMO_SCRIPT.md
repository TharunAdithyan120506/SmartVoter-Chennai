# Demo Script — Chennai District Election Management Portal

> 10-minute presentation walkthrough for DBMS Academic Project

---

## [1 min] Database Schema Overview

Open `database/schema.sql` and highlight:
- **10 tables** created in FK-dependency order
- Key constraints: `CHECK (age >= 18)` on voters, `CHECK (age >= 25)` on candidates
- `UNIQUE (voter_id)` on votes table ensures one vote per person
- Foreign keys cascade on update, restrict on delete

**Live query:**
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'election_db' ORDER BY table_name;
```

---

## [1 min] Triggers Demonstration

Open `database/triggers.sql` and explain:
1. **`before_vote_insert`** — Checks `has_voted` flag, raises error if already voted
2. **`after_vote_insert`** — Flips `has_voted = TRUE` automatically
3. **`after_vote_update_turnout`** — Increments constituency `voted_count`
4. **`after_voter_update_audit`** — Logs every voter edit to `audit_log` as JSON

**Live query:**
```sql
SELECT trigger_name FROM information_schema.triggers
WHERE trigger_schema = 'election_db';
```

---

## [1 min] Views & Live Query

```sql
SELECT * FROM v_turnout_summary LIMIT 5;
SELECT * FROM v_leading_candidates;
SELECT * FROM v_voter_card WHERE voter_id = 'TN/24/03/001234';
```

---

## [1 min] Index Usage Proof

```sql
EXPLAIN SELECT * FROM voters WHERE aadhar = '123412341234';
-- Show: key = idx_voters_aadhar

EXPLAIN SELECT candidate_id, COUNT(*) FROM votes
WHERE constituency_id = 3 GROUP BY candidate_id;
-- Show: key = idx_votes_constituency
```

---

## [1 min] Voter Portal — Login Demo

1. Open `http://localhost:5000`
2. Enter Aadhar: **1234 1234 1234**
3. Click "Send OTP" → OTP appears in toast notification (mock mode)
4. Enter OTP → Redirected to voter home page

---

## [1 min] Voter Portal — Map & Candidates

1. **Chennai Map** with 16 color-coded constituencies
2. Voter's constituency (Perambur) is highlighted/glowing
3. **Click any constituency** → right panel slides in with candidate list
4. **Click a candidate** → detail panel shows age, education, assets, criminal cases
5. **Navigate** to E-Voter Card → QR code generated, downloadable as PNG

---

## [2 min] Admin Portal — Polling Mode (Core Feature)

1. Log out → Log in as **admin / admin123**
2. Go to **Polling Mode**
3. Enter Voter ID: **TN/24/16/005678** → Verified (Priya Suresh, Saidapet)
4. Select a candidate from the grid (party color highlights selection)
5. Confirm → "This cannot be undone" warning
6. Cast Vote → Green checkmark pulse animation
7. Try same voter again → **"Already voted" error** (trigger working!)

---

## [1 min] Live Database Verification

```sql
-- Votes recorded
SELECT * FROM votes ORDER BY vote_id DESC LIMIT 5;

-- Voter marked as voted
SELECT voter_id, name, has_voted FROM voters WHERE voter_id = 'TN/24/16/005678';

-- Constituency turnout updated
SELECT name, voted_count FROM constituencies WHERE constituency_id = 16;
```

---

## [1 min] Audit Log & Stored Procedure

1. Go to **Voter List** in admin portal
2. Edit a voter's name/phone → Save
3. Show audit log in MySQL:

```sql
SELECT log_id, action, entity_id, old_value, new_value, performed_at
FROM audit_log ORDER BY log_id DESC LIMIT 3;
```

4. Show stored procedure:
```sql
CALL verify_voter('123412341234');
CALL get_constituency_results(16);
```

---

## Summary Slide Points

- ✅ 10 normalized tables (3NF)
- ✅ 13 foreign key constraints
- ✅ 4 triggers (double-vote prevention, audit logging)
- ✅ 4 stored procedures (atomic transactions)
- ✅ 4 views (turnout, results, voter card)
- ✅ 5 performance indexes
- ✅ Full-stack web portal with dark theme
- ✅ SVG constituency map with interactive panels
- ✅ QR-code voter cards
- ✅ 4-step polling wizard with real-time DB updates
