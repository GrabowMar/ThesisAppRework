import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, session, g
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'default-secret-key'),
    DATABASE='users.db',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,  # Set True in production with HTTPS
    SESSION_COOKIE_SAMESITE='Lax'
)

# Configure CORS for Vite frontend (port 6261)
CORS(
    app,
    supports_credentials=True,
    origins=['http://localhost:6261']
)

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Database setup
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

# Utility functions
def create_user(username, email, password):
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)',
            (username, email, password_hash, created_at)
        )
        db.commit()
        return True
    except sqlite3.IntegrityError as e:
        error_message = str(e)
        if 'username' in error_message:
            return {'error': 'Username already exists'}, 409
        elif 'email' in error_message:
            return {'error': 'Email already exists'}, 409
        return {'error': 'Database error'}, 500

def get_user_by_username(username):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    return cursor.fetchone()

def get_user_by_email(email):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    return cursor.fetchone()

def get_user_by_id(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, username, email, created_at FROM users WHERE id = ?', (user_id,))
    return cursor.fetchone()

# Authentication decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return {'error': 'Unauthorized'}, 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate input
    if not data or 'username' not in data or 'email' not in data or 'password' not in data:
        return {'error': 'Missing required fields'}, 400
    
    username = data['username'].strip()
    email = data['email'].strip().lower()
    password = data['password']
    
    # Basic validation
    if len(username) < 3:
        return {'error': 'Username must be at least 3 characters'}, 400
    if len(password) < 8:
        return {'error': 'Password must be at least 8 characters'}, 400
    
    # Create user
    result = create_user(username, email, password)
    if isinstance(result, tuple):  # Error occurred
        return result
    
    return {'message': 'User created successfully'}, 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or 'identifier' not in data or 'password' not in data:
        return {'error': 'Missing credentials'}, 400
    
    identifier = data['identifier'].strip()
    password = data['password']
    
    # Find user by username or email
    user = get_user_by_username(identifier) or get_user_by_email(identifier)
    
    if not user or not bcrypt.check_password_hash(user['password_hash'], password):
        return {'error': 'Invalid credentials'}, 401
    
    # Create session
    session['user_id'] = user['id']
    return {'message': 'Login successful'}, 200

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    session.pop('user_id', None)
    return {'message': 'Logout successful'}, 200

@app.route('/api/user', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return {'user': None}, 200
    
    user = get_user_by_id(user_id)
    if not user:
        session.pop('user_id', None)
        return {'user': None}, 200
    
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'created_at': user['created_at']
        }
    }), 200

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    if not user:
        return {'error': 'User not found'}, 404
    
    return jsonify({
        'dashboard_data': f'Welcome to your dashboard, {user["username"]}!',
        'user_info': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'joined': user['created_at']
        }
    }), 200

# Main execution
if __name__ == '__main__':
    init_db()  # Initialize database
    app.run(host='0.0.0.0', port=6261, debug=True)