# Chennai District Election Management Portal

> Full-stack DBMS Academic Project — Tamil Nadu Legislative Assembly Elections 2026

## 🏗️ Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Database   | MySQL 8.0                           |
| Backend    | Python 3.10+ / Flask                |
| Frontend   | Vanilla HTML + CSS + JavaScript     |
| Charts     | Chart.js (CDN)                      |
| QR Code    | qrcode.js (CDN)                     |
| Map        | Custom SVG map of Chennai           |

## 📁 Project Structure

```
election-portal/
├── backend/          # Flask API server
│   ├── app.py        # Entry point
│   ├── config.py     # DB config
│   ├── db.py         # MySQL helper
│   └── routes/       # auth, voter, admin routes
├── database/         # SQL + seed data
│   ├── schema.sql    # 10 tables
│   ├── triggers.sql  # 4 triggers
│   ├── procedures.sql# 4 stored procedures
│   ├── views.sql     # 4 views
│   ├── indexes.sql   # 5 indexes
│   ├── seed/         # 6 CSV files
│   └── load_seed.py  # Data loader
└── frontend/         # Static HTML/CSS/JS
    ├── index.html    # Login page
    ├── voter/        # Voter portal (map, e-voter card, profile)
    ├── admin/        # Admin portal (dashboard, voters, candidates, polling, results)
    └── css/js/       # Styles and scripts
```

## 🚀 Setup Instructions

### 1. Database Setup

```bash
# Create the database and load all data
mysql -u root -p < database/schema.sql

# Install Python MySQL connector
pip install mysql-connector-python

# Edit database/load_seed.py or backend/config.py with your MySQL credentials
# Then run:
python database/load_seed.py
```

### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Set environment variables (optional — defaults work for local dev)
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DB=election_db

# Run the Flask server
python app.py
```

The server starts at `http://localhost:5000`.

### 3. Frontend

The frontend is served automatically by Flask at `http://localhost:5000`.
Just open the URL in your browser.

## 🔑 Demo Credentials

### Voter Login (Aadhar + OTP)
| Voter          | Aadhar           | Constituency |
|----------------|------------------|--------------|
| Arjun Ramasamy | 1234 1234 1234   | Perambur     |
| Priya Suresh   | 5678 5678 5678   | Saidapet     |
| Senthil Kumar  | 9012 9012 9012   | Egmore       |

OTP is mocked — the OTP value is returned in the API response.

### Admin Login
| Username | Password  | Role         |
|----------|-----------|--------------|
| admin    | admin123  | SUPER_ADMIN  |

## 📊 Database Design

### 10 Tables

| Table             | Description                              | Rows  |
|-------------------|------------------------------------------|-------|
| `parties`         | Political parties with colors/alliance   | 7     |
| `constituencies`  | 16 Chennai constituencies                | 16    |
| `polling_booths`  | 3 booths per constituency                | 48    |
| `voters`          | Registered voters with Aadhar            | 40    |
| `candidates`      | 7 candidates per constituency            | 112   |
| `admins`          | Election officers                        | 5     |
| `votes`           | Append-only vote records                 | 0+    |
| `otp_sessions`    | OTP authentication sessions              | 0+    |
| `audit_log`       | Auto-logged voter record changes         | 0+    |
| `election_config` | System configuration key-value pairs     | 3     |

### ER Diagram (Text)

```
parties ←──── candidates ────→ constituencies
                                  ↑     ↑
                                  │     │
              voters ─────────────┘     │
                ↑                       │
                │                       │
              votes ────────────────────┘
                │
              admins ────→ audit_log
```

- `candidates` references `parties` and `constituencies`
- `voters` references `constituencies` and `polling_booths`
- `votes` references `voters`, `candidates`, `constituencies`, `polling_booths`, `admins`
- `audit_log` references `admins`
- `election_config` references `admins`

### DBMS Concepts Demonstrated

| Concept                | Where                                                  |
|------------------------|--------------------------------------------------------|
| Normalization (3NF)    | All tables — no transitive dependencies                |
| Foreign Keys           | 13 FK constraints across tables                        |
| CHECK Constraints      | Voter age ≥ 18, candidate age ≥ 25, voted ≤ total     |
| Triggers               | Double-vote prevention, auto-mark voter, turnout count, audit log |
| Stored Procedures      | cast_vote (transaction), verify_voter, get_results, generate_otp |
| Views                  | Turnout summary, candidate results, voter card, leading candidates |
| Indexes                | On aadhar, constituency_id, expires_at, admin_id       |
| Transactions           | ACID-compliant vote casting with rollback              |
| Parameterized Queries  | All SQL uses %s placeholders (no injection)            |

### Normalization Statement

All tables are in **Third Normal Form (3NF)**:
- **1NF**: All columns contain atomic values; no repeating groups
- **2NF**: All non-key attributes depend on the entire primary key (no partial dependencies)
- **3NF**: No transitive dependencies — e.g., party info is in `parties`, not duplicated in `candidates`

## 🌐 Deployment

### Deploy to Render (Easiest)
This project is configured for one-click deployment on Render.
1. Push this repo to GitHub.
2. Go to [Render Dashboard](https://dashboard.render.com).
3. Create a **New Blueprint Instance**.
4. Select this repository.
5. Click **Apply**.

### Deploy with Docker
```bash
docker-compose up --build
```

## 📝 License

Academic project — Tamil Nadu Legislative Assembly 2026 (fictional scenario).
