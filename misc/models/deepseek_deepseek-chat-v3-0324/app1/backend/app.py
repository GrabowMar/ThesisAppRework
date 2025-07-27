# 1. Imports
from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import sqlite3
import os
from datetime import datetime

# 2. App Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()  # Random secret key for session management
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS

# Configure CORS to allow requests from Vite frontend
CORS(app, supports_credentials=True, origins=["http://localhost:6191"])

bcrypt = Bcrypt(app)

# 3. Database Setup
def init_db():
    """Initialize the SQLite database with Users table"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

# 4. Utility and helper functions
def login_required(f):
    """Decorator to protect routes that require authentication"""
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def validate_user_data(data, is_login=False):
    """Validate user input for registration/login"""
    errors = {}
    
    if not is_login:
        if not data.get('username') or len(data['username']) < 3:
            errors['username'] = 'Username must be at least 3 characters'
        if not data.get('email') or '@' not in data['email']:
            errors['email'] = 'Valid email is required'
    
    if not data.get('password') or len(data['password']) < 6:
        errors['password'] = 'Password must be at least 6 characters'
    
    return errors if errors else None

# 5. API Routes
@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate input
    errors = validate_user_data(data)
    if errors:
        return jsonify({'errors': errors}), 400
    
    # Check for existing user
    conn = get_db_connection()
    existing_user = conn.execute(
        'SELECT * FROM Users WHERE username = ? OR email = ?',
        (data['username'], data['email'])
    ).fetchone()
    
    if existing_user:
        conn.close()
        return jsonify({'errors': {'username': 'Username or email already exists'}}), 409
    
    # Hash password and create user
    password_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    created_at = datetime.utcnow().isoformat()
    
    conn.execute(
        'INSERT INTO Users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)',
        (data['username'], data['email'], password_hash, created_at)
    )
    conn.commit()
    
    # Get the new user's ID
    user = conn.execute(
        'SELECT id, username, email FROM Users WHERE username = ?',
        (data['username'],)
    ).fetchone()
    
    conn.close()
    
    # Start session
    session['user_id'] = user['id']
    
    return jsonify({
        'message': 'User registered successfully',
        'user': dict(user)
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and create session"""
    data = request.get_json()
    
    # Validate input
    errors = validate_user_data(data, is_login=True)
    if errors:
        return jsonify({'errors': errors}), 400
    
    # Find user by username or email
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM Users WHERE username = ? OR email = ?',
        (data.get('username_or_email'), data.get('username_or_email'))
    ).fetchone()
    conn.close()
    
    # Verify user exists and password is correct
    if not user or not bcrypt.check_password_hash(user['password_hash'], data['password']):
        return jsonify({'errors': {'auth': 'Invalid credentials'}}), 401
    
    # Start session
    session['user_id'] = user['id']
    
    return jsonify({
        'message': 'Logged in successfully',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email']
        }
    })

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Destroy user session"""
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/user', methods=['GET'])
def get_current_user():
    """Get current user data if session exists"""
    if 'user_id' not in session:
        return jsonify({'user': None}), 200
    
    conn = get_db_connection()
    user = conn.execute(
        'SELECT id, username, email FROM Users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()
    
    if not user:
        session.pop('user_id', None)
        return jsonify({'user': None}), 200
    
    return jsonify({'user': dict(user)})

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    """Protected endpoint example"""
    return jsonify({
        'message': 'Welcome to your dashboard!',
        'secret_data': 'This is protected content'
    })

# 6. Main execution
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=6191, debug=True)