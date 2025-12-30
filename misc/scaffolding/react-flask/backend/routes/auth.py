# Authentication Routes - Login, Register, Logout, and User Profile
# All routes use the auth_bp blueprint with /api/auth prefix
from functools import wraps
from datetime import datetime, timedelta
from flask import jsonify, request, current_app
import jwt
import os

from routes import auth_bp
from models import db, User


# ============================================================================
# JWT TOKEN UTILITIES
# ============================================================================

def get_secret_key():
    """Get the JWT secret key from environment or app config."""
    return os.environ.get('JWT_SECRET_KEY', 
           os.environ.get('SECRET_KEY', 
           current_app.config.get('SECRET_KEY', 'dev-secret-key')))


def generate_token(user_id, expires_hours=24):
    """Generate a JWT token for a user."""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=expires_hours),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, get_secret_key(), algorithm='HS256')


def decode_token(token):
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ============================================================================
# TOKEN REQUIRED DECORATOR - Use this to protect routes
# ============================================================================

def token_required(f):
    """Decorator to require valid JWT token for route access.
    
    Usage:
        @user_bp.route('/protected')
        @token_required
        def protected_route(current_user):
            return jsonify({'user': current_user.username})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        
        if not token:
            return jsonify({'error': 'Token is required'}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        current_user = User.query.get(payload['user_id'])
        if not current_user or not current_user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated


def token_optional(f):
    """Decorator for routes that work with or without authentication.
    
    If valid token is provided, current_user is the User object.
    If no token or invalid token, current_user is None.
    
    Usage:
        @user_bp.route('/items')
        @token_optional
        def list_items(current_user):
            if current_user:
                return jsonify({'user_items': ...})
            return jsonify({'public_items': ...})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = None
        
        # Try to get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload:
                user = User.query.get(payload['user_id'])
                if user and user.is_active:
                    current_user = user
        
        return f(current_user, *args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to require admin user for route access.
    
    Usage:
        @admin_bp.route('/admin-only')
        @admin_required
        def admin_route(current_user):
            return jsonify({'admin': current_user.username})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        
        if not token:
            return jsonify({'error': 'Token is required'}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        current_user = User.query.get(payload['user_id'])
        if not current_user or not current_user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(current_user, *args, **kwargs)
    return decorated


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account.
    
    Request body:
        {
            "username": "string (required)",
            "password": "string (required)", 
            "email": "string (optional)"
        }
    
    Returns:
        201: User created successfully with token
        400: Validation error (missing fields, user exists)
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip() or None
    
    # Validation
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if user exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if email and User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create user
    user = User(username=username, email=email)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    # Generate token for immediate login
    token = generate_token(user.id)
    
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'token': token
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token.
    
    Request body:
        {
            "username": "string (required)",
            "password": "string (required)"
        }
    
    Returns:
        200: Login successful with token and user data
        401: Invalid credentials
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    # Find user
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 401
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate token
    token = generate_token(user.id)
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'token': token
    })


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current authenticated user's profile.
    
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        200: User profile data
        401: Invalid or missing token
    """
    return jsonify({'user': current_user.to_dict()})


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Logout the current user.
    
    Note: JWT tokens are stateless, so this is primarily for client-side cleanup.
    For production, consider implementing a token blacklist.
    
    Returns:
        200: Logout successful
    """
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """Change the current user's password.
    
    Request body:
        {
            "current_password": "string (required)",
            "new_password": "string (required)"
        }
    
    Returns:
        200: Password changed successfully
        400: Validation error
        401: Current password incorrect
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password are required'}), 400
    
    if not current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    
    current_user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Password changed successfully'})
