# 1. Imports
from flask import Flask, request, jsonify, session, redirect
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import sqlite3
import os
from datetime import timedelta

# 2. App Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
CORS(app, supports_credentials=True)
bcrypt = Bcrypt(app)

# 3. Database Setup
DATABASE_URL = os.getenv('DATABASE_URL')
def init_db():
    with sqlite3.connect(DATABASE_URL) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

# 4. Utility and Helper Functions
def hash_password(password):
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(hash, password):
    return bcrypt.check_password_hash(hash, password)

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM Users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM Users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

# 5. API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"message": "Missing required fields"}), 400

    if get_user_by_email(email):
        return jsonify({"message": "Email already registered"}), 400

    password_hash = hash_password(password)

    conn = get_db_connection()
    conn.execute('INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)',
                 (username, email, password_hash))
    conn.commit()
    conn.close()

    return jsonify({"message": "User registered successfully"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = get_user_by_email(email)
    if not user or not check_password(user['password_hash'], password):
        return jsonify({"message": "Invalid credentials"}), 401

    session['user_id'] = user['id']
    return jsonify({"message": "Login successful"}), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Logout successful"}), 200

@app.route('/api/user', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"message": "User not logged in"}), 401

    user = get_user_by_id(user_id)
    return jsonify({
        "id": user['id'],
        "username": user['username'],
        "email": user['email']
    }), 200

@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"message": "User not logged in"}), 401

    user = get_user_by_id(user_id)
    return jsonify({"message": f"Welcome to the dashboard, {user['username']}!"}), 200

# 6. Main Execution
if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5001)