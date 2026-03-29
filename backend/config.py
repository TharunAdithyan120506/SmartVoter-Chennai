import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'tharun')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'password123')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'election_db')
    SESSION_TIMEOUT = 3600  # 1 hour in seconds
    OTP_EXPIRY_MINUTES = 10
    # For demo: print OTP to console instead of sending SMS
    MOCK_OTP = os.environ.get('MOCK_OTP', 'True') == 'True'
