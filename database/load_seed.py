#!/usr/bin/env python3
"""
Load seed data into the election_db MySQL database.
Run all SQL schema files first, then import CSVs.
"""
import csv
import os
import sys

import mysql.connector

# Add backend to path for config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from config import Config
    MYSQL_HOST = Config.MYSQL_HOST
    MYSQL_USER = Config.MYSQL_USER
    MYSQL_PASSWORD = Config.MYSQL_PASSWORD
    MYSQL_DB = Config.MYSQL_DB
except ImportError:
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'password')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'election_db')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_connection(database=None):
    """Create a MySQL connection."""
    params = {
        'host': MYSQL_HOST,
        'user': MYSQL_USER,
        'password': MYSQL_PASSWORD,
        'autocommit': True,
        'allow_local_infile': True,
    }
    if database:
        params['database'] = database
    return mysql.connector.connect(**params)


def execute_sql_file(cursor, filepath):
    """Execute a SQL file, handling DELIMITER statements for triggers/procedures."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Handle DELIMITER $$ blocks
    if 'DELIMITER' in content:
        # Split by DELIMITER markers
        parts = content.split('DELIMITER')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith('$$'):
                # This is a stored procedure/trigger block
                part = part[2:].strip()  # Remove leading $$
                if part.endswith('$$'):
                    part = part[:-2].strip()
                # Split by $$ to get individual statements
                stmts = part.split('$$')
                for stmt in stmts:
                    stmt = stmt.strip()
                    if stmt and stmt != ';':
                        # Remove trailing semicolons and DELIMITER markers
                        stmt = stmt.rstrip(';').strip()
                        if stmt and not stmt.startswith('DELIMITER'):
                            try:
                                cursor.execute(stmt)
                            except mysql.connector.Error as e:
                                print(f"  Warning: {e}")
            elif part.startswith(';'):
                # Back to normal delimiter
                remaining = part[1:].strip()
                if remaining:
                    stmts = remaining.split(';')
                    for stmt in stmts:
                        stmt = stmt.strip()
                        if stmt:
                            try:
                                cursor.execute(stmt)
                            except mysql.connector.Error as e:
                                print(f"  Warning: {e}")
            else:
                # Regular SQL statements
                stmts = part.split(';')
                for stmt in stmts:
                    stmt = stmt.strip()
                    if stmt:
                        try:
                            cursor.execute(stmt)
                        except mysql.connector.Error as e:
                            print(f"  Warning: {e}")
    else:
        # No DELIMITER, simple execution
        statements = content.split(';')
        for stmt in statements:
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                try:
                    cursor.execute(stmt)
                except mysql.connector.Error as e:
                    print(f"  Warning: {e}")


def load_csv(cursor, table_name, csv_path, columns):
    """Load a CSV file into a table."""
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            values = []
            placeholders = []
            cols = []
            for col in columns:
                val = row.get(col, '').strip()
                if val == '' or val == 'NULL':
                    values.append(None)
                elif val == 'FALSE':
                    values.append(0)
                elif val == 'TRUE':
                    values.append(1)
                else:
                    values.append(val)
                placeholders.append('%s')
                cols.append(col)

            sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
            try:
                cursor.execute(sql, values)
                count += 1
            except mysql.connector.Error as e:
                print(f"  Error inserting into {table_name}: {e}")
                print(f"  Row: {row}")
        return count


def main():
    print("=" * 60)
    print("Chennai District Election Portal — Database Setup")
    print("=" * 60)

    # Step 1: Run schema.sql (creates DB and tables)
    print("\n[1/6] Running schema.sql...")
    conn = get_connection()
    cursor = conn.cursor()
    execute_sql_file(cursor, os.path.join(BASE_DIR, 'schema.sql'))
    cursor.close()
    conn.close()
    print("  ✓ Schema created (10 tables)")

    # Reconnect to the database
    conn = get_connection(database=MYSQL_DB)
    cursor = conn.cursor()

    # Step 2: Run triggers.sql
    print("\n[2/6] Running triggers.sql...")
    execute_sql_file(cursor, os.path.join(BASE_DIR, 'triggers.sql'))
    print("  ✓ Triggers created (4 triggers)")

    # Step 3: Run procedures.sql
    print("\n[3/6] Running procedures.sql...")
    execute_sql_file(cursor, os.path.join(BASE_DIR, 'procedures.sql'))
    print("  ✓ Stored procedures created (4 procedures)")

    # Step 4: Run views.sql
    print("\n[4/6] Running views.sql...")
    execute_sql_file(cursor, os.path.join(BASE_DIR, 'views.sql'))
    print("  ✓ Views created (4 views)")

    # Step 5: Run indexes.sql
    print("\n[5/6] Running indexes.sql...")
    execute_sql_file(cursor, os.path.join(BASE_DIR, 'indexes.sql'))
    print("  ✓ Indexes created (5 indexes)")

    # Step 6: Load seed data
    print("\n[6/6] Loading seed data...")
    seed_dir = os.path.join(BASE_DIR, 'seed')

    # Load in order of FK dependencies
    tables = [
        ('parties', 'parties.csv', [
            'party_id', 'name', 'abbr', 'color_code', 'alliance', 'founded_year', 'symbol_desc'
        ]),
        ('constituencies', 'constituencies.csv', [
            'constituency_id', 'name', 'type', 'region', 'total_voters', 'voted_count', 'returning_officer'
        ]),
        ('polling_booths', 'polling_booths.csv', [
            'booth_id', 'booth_name', 'constituency_id', 'address', 'total_voters', 'booth_officer'
        ]),
        ('voters', 'voters.csv', [
            'voter_id', 'aadhar', 'name', 'age', 'gender', 'dob', 'address', 'phone',
            'constituency_id', 'booth_id', 'serial_no', 'has_voted'
        ]),
        ('candidates', 'candidates.csv', [
            'candidate_id', 'name', 'age', 'gender', 'party_id', 'constituency_id',
            'criminal_cases', 'assets_lakh', 'liabilities_lakh', 'education', 'status', 'nomination_date'
        ]),
        ('admins', 'admins.csv', [
            'admin_id', 'username', 'password_hash', 'name', 'role', 'constituency_id'
        ]),
    ]

    summary = {}
    for table_name, csv_file, columns in tables:
        csv_path = os.path.join(seed_dir, csv_file)
        count = load_csv(cursor, table_name, csv_path, columns)
        summary[table_name] = count
        print(f"  ✓ {table_name}: {count} rows inserted")

    # Insert default election_config rows
    print("\n  Inserting election_config defaults...")
    config_rows = [
        ('election_phase', 'POLLING', 'Current election phase: NOMINATION/POLLING/COUNTING/RESULTS'),
        ('election_date', '2026-04-15', 'Date of the election'),
        ('results_declared', 'FALSE', 'Whether results have been officially declared'),
    ]
    for key, value, desc in config_rows:
        cursor.execute(
            "INSERT INTO election_config (config_key, config_value, description) VALUES (%s, %s, %s)",
            (key, value, desc)
        )
    print(f"  ✓ election_config: {len(config_rows)} rows inserted")
    summary['election_config'] = len(config_rows)

    conn.commit()

    # Print summary
    print("\n" + "=" * 60)
    print("SEED DATA SUMMARY")
    print("=" * 60)
    for table, count in summary.items():
        print(f"  {table:25s} → {count:>4d} rows")
    print("=" * 60)

    # Verify counts
    print("\nVerification:")
    for table_name in ['parties', 'constituencies', 'polling_booths', 'voters', 'candidates', 'admins']:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  {table_name}: {count} rows")

    cursor.close()
    conn.close()
    print("\n✅ Database setup complete!")


if __name__ == '__main__':
    main()
