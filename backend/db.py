import mysql.connector
from flask import g
from config import Config


def get_db():
    """Get a database connection, creating one if it doesn't exist."""
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            autocommit=False
        )
    return g.db


def close_db(e=None):
    """Close the database connection at app teardown."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_one(sql, params=None):
    """Execute SQL and return first row as dict."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    result = cursor.fetchone()
    cursor.close()
    return result


def query_all(sql, params=None):
    """Execute SQL and return all rows as list of dicts."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    result = cursor.fetchall()
    cursor.close()
    return result


def execute(sql, params=None):
    """Execute INSERT/UPDATE/DELETE. Returns lastrowid."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(sql, params or ())
    db.commit()
    rowid = cursor.lastrowid
    cursor.close()
    return rowid


def call_procedure(proc_name, args=()):
    """Call a stored procedure and return result sets."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.callproc(proc_name, args)
    results = []
    for result in cursor.stored_results():
        results.append(result.fetchall())
    db.commit()
    cursor.close()
    return results
