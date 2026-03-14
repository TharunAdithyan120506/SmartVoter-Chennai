import os
import sys

from flask import Flask, send_from_directory
from flask_cors import CORS

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from db import close_db
from routes.auth import auth_bp
from routes.voter import voter_bp
from routes.admin import admin_bp

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config.from_object(Config)
CORS(app, supports_credentials=True)

app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(voter_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.teardown_appcontext(close_db)


@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
