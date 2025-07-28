# Flask Authentication API Documentation

This document provides a complete implementation of a secure Flask backend for user authentication, including registration, login, session management, and protected routes.

## Table of Contents
1. [System Overview](#system-overview)
2. [Setup Instructions](#setup-instructions)
3. [Database Schema](#database-schema)
4. [API Endpoints](#api-endpoints)
5. [Implementation Details](#implementation-details)
6. [Security Considerations](#security-considerations)
7. [Usage Examples](#usage-examples)

## System Overview

This Flask-based authentication system provides:
- Secure user registration with password hashing
- Session-based authentication
- Protected routes
- Cross-origin resource sharing (CORS) support
- SQLite database for user storage

## Setup Instructions

### 1. Install Dependencies

Create a `requirements.txt` file with the following content:

```txt
Flask==3.0.0
Flask-CORS==4.0.0
Flask-Bcrypt==1.0.1
python-dotenv==1.0.0
```

Install them using:
```bash
pip install -r requirements.txt
```

### 2. Database Initialization

The system will automatically create a SQLite database file (`auth.db`) when first run.

## Database Schema

The system uses a single `users` table with the following structure:

| Column        | Type        | Description                     |
|---------------|-------------|---------------------------------|
| id            | INTEGER     | Primary key, auto-increment     |
| username      | TEXT        | Unique username                |
| email         | TEXT        | Unique email address           |
| password_hash | TEXT        | BCrypt hashed password         |
| created_at    | DATETIME    | Timestamp of account creation   |

## Implementation Details

### Complete `app.py` Implementation

```python
# 1. Imports
from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS, cross_origin
from flask_bcrypt import Bcrypt
import sqlite3
from datetime import datetime
import os
from functools import wraps

# 2. App Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session lifetime

# Configure CORS to work with your Vite frontend (port 5505)
CORS(
    app,
    resources={r"/api/*": {"origins": "http://localhost:5505"}},
    supports_credentials=True
)

bcrypt = Bcrypt(app)

# 3. Database Setup
def get_db_connection():
    conn = sqlite3.connect('auth.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()

# 4. Utility and helper functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def validate_registration_data(data):
    errors = {}
    if not data.get('username'):
        errors['username'] = 'Username is required'
    if not data.get('email'):
        errors['email'] = 'Email is required'
    elif '@' not in data['email']:
        errors['email'] = 'Invalid email format'
    if not data.get('password'):
        errors['password'] = 'Password is required'
    elif len(data['password']) < 8:
        errors['password'] = 'Password must be at least 8 characters'
    return errors

# 5. API Routes
@app.route('/api/register', methods=['POST'])
@cross_origin(supports_credentials=True)
def register():
    data = request.get_json()
    
    # Validate input
    errors = validate_registration_data(data)
    if errors:
        return jsonify({'errors': errors}), 400
    
    # Check for existing user
    with get_db_connection() as conn:
        existing_user = conn.execute(
            'SELECT * FROM users WHERE username = ? OR email = ?',
            (data['username'], data['email'])
        ).fetchone()
        
    if existing_user:
        return jsonify({
            'errors': {
                'username': 'Username or email already exists'
            }
        }), 400
    
    # Hash password and create user
    password_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    with get_db_connection() as conn:
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (data['username'], data['email'], password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
    
    # Automatically log in the user after registration
    session['user_id'] = user_id
    
    return jsonify({
        'message': 'User registered successfully',
        'user': {
            'id': user_id,
            'username': data['username'],
            'email': data['email']
        }
    }), 201

@app.route('/api/login', methods=['POST'])
@cross_origin(supports_credentials=True)
def login():
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Find user by email
    with get_db_connection() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?',
            (data['email'],)
        ).fetchone()
    
    if not user or not bcrypt.check_password_hash(user['password_hash'], data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Create session
    session['user_id'] = user['id']
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email']
        }
    })

@app.route('/api/logout', methods=['POST'])
@cross_origin(supports_credentials=True)
@login_required
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logout successful'})

@app.route('/api/user', methods=['GET'])
@cross_origin(supports_credentials=True)
@login_required
def get_current_user():
    with get_db_connection() as conn:
        user = conn.execute(
            'SELECT id, username, email, created_at FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'created_at': user['created_at']
        }
    })

@app.route('/api/dashboard', methods=['GET'])
@cross_origin(supports_credentials=True)
@login_required
def dashboard():
    # This is a protected route that returns personalized dashboard data
    with get_db_connection() as conn:
        user = conn.execute(
            'SELECT id, username FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
    
    return jsonify({
        'message': f'Welcome to your dashboard, {user["username"]}!',
        'data': {
            'stats': {
                'visits': 42,
                'notifications': 5,
                'messages': 3
            }
        }
    })

# 6. Main execution
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5005, debug=True)
```

## Security Considerations

1. **Password Hashing**: Uses BCrypt with salt for secure password storage
2. **Session Security**:
   - Session cookies are HTTP-only
   - SameSite=Lax policy to prevent CSRF
   - 1-hour session expiration
3. **Input Validation**: All user input is validated
4. **Error Handling**: Proper error responses without revealing sensitive information
5. **CORS**: Strictly configured to work only with the Vite frontend (port 5505)

## API Endpoints

### 1. User Registration
- **Endpoint**: `POST /api/register`
- **Request Body**:
  ```json
  {
    "username": "example_user",
    "email": "user@example.com",
    "password": "securePassword123"
  }
  ```
- **Success Response**:
  ```json
  {
    "message": "User registered successfully",
    "user": {
      "id": 1,
      "username": "example_user",
      "email": "user@example.com"
    }
  }
  ```

### 2. User Login
- **Endpoint**: `POST /api/login`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "securePassword123"
  }
  ```
- **Success Response**:
  ```json
  {
    "message": "Login successful",
    "user": {
      "id": 1,
      "username": "example_user",
      "email": "user@example.com"
    }
  }
  ```

### 3. Get Current User
- **Endpoint**: `GET /api/user`
- **Success Response**:
  ```json
  {
    "user": {
      "id": 1,
      "username": "example_user",
      "email": "user@example.com",
      "created_at": "2023-01-01 12:00:00"
    }
  }
  ```

### 4. Logout
- **Endpoint**: `POST /api/logout`
- **Success Response**:
  ```json
  {
    "message": "Logout successful"
  }
  ```

### 5. Protected Dashboard
- **Endpoint**: `GET /api/dashboard`
- **Success Response**:
  ```json
  {
    "message": "Welcome to your dashboard, example_user!",
    "data": {
      "stats": {
        "visits": 42,
        "notifications": 5,
        "messages": 3
      }
    }
  }
  ```

## Usage Examples

### Frontend Integration (React + Axios)

```javascript
import axios from 'axios';

// Configure axios to send credentials with all requests
axios.defaults.withCredentials = true;

// Example registration
async function register(username, email, password) {
  try {
    const response = await axios.post('http://localhost:5005/api/register', {
      username,
      email,
      password
    });
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
}

// Example login
async function login(email, password) {
  try {
    const response = await axios.post('http://localhost:5005/api/login', {
      email,
      password
    });
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
}

// Example protected request
async function getDashboardData() {
  try {
    const response = await axios.get('http://localhost:5005/api/dashboard');
    return response.data;
  } catch (error) {
    throw error.response.data;
  }
}
```

### Environment Variables

For production, consider using environment variables:

```bash
# .env file
SECRET_KEY=your-very-secret-key-here
```

This completes the comprehensive backend implementation for the Login application with all specified requirements.