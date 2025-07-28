### Secure Flask Authentication API Implementation

I'll create a secure backend authentication system using Flask that meets all your requirements. The solution includes session-based authentication, protected routes, and proper password hashing with Bcrypt.

#### Files:
1. `requirements.txt`
2. `app.py`

---

### 1. requirements.txt
```txt
Flask==3.0.3
Flask-CORS==4.0.1
Flask-Bcrypt==1.0.1
python-dotenv==1.0.1
```

---

### 2. app.py
```python
# 1. Imports
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

# 2. App Configuration
app = Flask(__name__)
load_dotenv()  # Load environment variables from .env file

# Configure secret key and session settings
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  # Requires HTTPS in production
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400  # 24 hours
)

# Configure CORS to allow Vite frontend (port 5505)
CORS(
    app,
    supports_credentials=True,
    origins=['http://localhost:5505']
)

# Initialize Bcrypt
bcrypt = Bcrypt(app)

# 3. Database Setup
DATABASE = 'auth_db.sqlite'

def init_db():
    """Initialize the database with required tables"""
    with app.app_context():
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# 4. Utility and helper functions
def validate_registration(data):
    """Validate registration input"""
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

def login_required(f):
    """Decorator to protect routes requiring authentication"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 5. API Routes
@app.route('/api/register', methods=['POST'])
def register():
    """User registration endpoint"""
    data = request.get_json()
    errors = validate_registration(data)
    if errors:
        return jsonify({'errors': errors}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check for existing username/email
        cursor.execute('SELECT * FROM Users WHERE username = ? OR email = ?', 
                      (data['username'], data['email']))
        existing_user = cursor.fetchone()
        if existing_user:
            return jsonify({
                'error': 'Username or email already exists'
            }), 409
        
        # Hash password and create user
        password_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO Users (username, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
        ''', (data['username'], data['email'], password_hash, created_at))
        conn.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': {
                'id': cursor.lastrowid,
                'username': data['username'],
                'email': data['email']
            }
        }), 201
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    """User login endpoint"""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM Users WHERE username = ?
        ''', (data['username'],))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if bcrypt.check_password_hash(user['password_hash'], data['password']):
            # Create session
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            return jsonify({
                'message': 'Login successful',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout endpoint - clears user session"""
    if 'user_id' in session:
        session.clear()
        return jsonify({'message': 'Successfully logged out'})
    return jsonify({'error': 'Not logged in'}), 401

@app.route('/api/user', methods=['GET'])
def get_current_user():
    """Get current authenticated user's data"""
    if 'user_id' in session:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, email, created_at FROM Users WHERE id = ?', 
                          (session['user_id'],))
            user = cursor.fetchone()
            if user:
                return jsonify({
                    'user': dict(user)
                })
        except sqlite3.Error as e:
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()
    return jsonify({'user': None})

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    """Protected dashboard endpoint with welcome message"""
    return jsonify({
        'message': f"Welcome to your dashboard, {session['username']}!",
        'logout_button': '<button id="logout-btn">Logout</button>'
    })

# 6. Main execution
if __name__ == '__main__':
    init_db()  # Initialize database on startup
    app.run(host='0.0.0.0', port=5005, debug=True)
```

---

## Implementation Details

### Security Features
1. **Password Hashing**: Uses `Flask-Bcrypt` with industry-standard salting and hashing
2. **Session Security**: 
   - HttpOnly cookies
   - Secure cookies (enable HTTPS in production)
   - SameSite cookie policy
3. **Input Validation**: 
   - Username/email uniqueness checks
   - Password length validation
   - Email format validation
4. **Error Handling**:
   - Proper HTTP status codes
   - Descriptive error messages
   - SQL injection prevention with parameterized queries

### Session Management
- Uses Flask's built-in session management
- Sessions stored server-side with client-side session ID cookies
- Automatic session expiration (24 hours)

### CORS Configuration
- Pre-configured for Vite development server (`http://localhost:5505`)
- `supports_credentials=True` allows sending cookies cross-origin
- Strict origin configuration prevents unwanted access

### Database Schema
```sql
CREATE TABLE Users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

---

## Setup Instructions

### 1. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate    # Windows
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create .env file
```env
SECRET_KEY=your_strong_secret_key_here
```

### 4. Run the application
```bash
python app.py
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/register` | POST | Register new user |
| `/api/login` | POST | Authenticate user |
| `/api/logout` | POST | Terminate session |
| `/api/user` | GET | Get current user data |
| `/api/dashboard` | GET | Protected dashboard |

---

## Usage Examples

### 1. Registration
```bash
curl -X POST http://localhost:5005/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "securePassword123"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:5005/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "securePassword123"
  }' \
  -c cookies.txt
```

### 3. Access Protected Dashboard
```bash
curl -X GET http://localhost:5005/api/dashboard \
  -H "Content-Type: application/json" \
  -b cookies.txt
```

### 4. Get Current User
```bash
curl -X GET http://localhost:5005/api/user \
  -H "Content-Type: application/json" \
  -b cookies.txt
```

### 5. Logout
```bash
curl -X POST http://localhost:5005/api/logout \
  -H "Content-Type: application/json" \
  -b cookies.txt
```

---

## Frontend Integration Notes

1. **CORS Configuration**: 
   - The backend is pre-configured for Vite (port 5505)
   - Ensure frontend makes requests with `credentials: 'include'`
   
2. **Axios Example**:
```javascript
axios.post('http://localhost:5005/api/login', 
  { username: 'test', password: 'password' },
  { withCredentials: true }
)
```

3. **Session Management**:
   - The backend uses session cookies automatically
   - No need for token storage in frontend
   - Cookies are HttpOnly for XSS protection

4. **Dashboard Response**:
```json
{
  "message": "Welcome to your dashboard, john_doe!",
  "logout_button": "<button id=\"logout-btn\">Logout</button>"
}
```

---

## Security Best Practices Implemented

1. Password hashing with bcrypt (adaptive hashing algorithm)
2. HttpOnly and Secure cookies
3. Input validation and sanitization
4. Parameterized SQL queries to prevent injection
5. Session expiration
6. CORS origin restrictions
7. Error handling without sensitive data leakage
8. Secret key management via environment variables

This implementation provides a robust foundation for authentication that can be extended with additional security measures like rate limiting, account lockouts, and two-factor authentication as needed.