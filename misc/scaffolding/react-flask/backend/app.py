# Flask scaffold with built-in authentication system
# AI-generated code will extend this with app-specific features
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from datetime import datetime, timedelta
from functools import wraps
import bcrypt
import os
import logging
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# JWT configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

db = SQLAlchemy()
jwt = JWTManager()

# Token blocklist for logout functionality
token_blocklist = set()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in token_blocklist

# ============================================================================
# AUTH MODELS
# ============================================================================

class User(db.Model):
    """User model with authentication and role support."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Password reset fields
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def check_password(self, password):
        """Verify the password against the stored hash."""
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            self.password_hash.encode('utf-8')
        )
    
    def generate_reset_token(self):
        """Generate a password reset token valid for 1 hour."""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token
    
    def clear_reset_token(self):
        """Clear the password reset token."""
        self.reset_token = None
        self.reset_token_expires = None
    
    def to_dict(self, include_email=False):
        """Serialize user to dictionary."""
        data = {
            'id': self.id,
            'username': self.username,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        if include_email:
            data['email'] = self.email
        return data

# ============================================================================
# AUTH DECORATORS
# ============================================================================

def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        return f(*args, **kwargs)
    return decorated

def active_user_required(f):
    """Decorator to require an active (non-deactivated) user."""
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        return f(*args, **kwargs)
    return decorated

def handle_errors(f):
    """Decorator for consistent error handling."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated

# ============================================================================
# AUTH ROUTES
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
@handle_errors
def register():
    """Register a new user account."""
    data = request.get_json()
    
    # Validation
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not username or len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if len(username) > 80:
        return jsonify({'error': 'Username must be less than 80 characters'}), 400
    if not username.replace('_', '').replace('-', '').isalnum():
        return jsonify({'error': 'Username can only contain letters, numbers, underscores, and hyphens'}), 400
    
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email is required'}), 400
    
    if not password or len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    # Check uniqueness
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409
    
    # Create user
    user = User(username=username, email=email)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    logger.info(f"New user registered: {username}")
    
    # Auto-login after registration
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict(include_email=True),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201

@app.route('/api/auth/login', methods=['POST'])
@handle_errors
def login():
    """Authenticate user and return tokens."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    # Find user by username or email
    user = User.query.filter(
        (User.username == username) | (User.email == username.lower())
    ).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    logger.info(f"User logged in: {user.username}")
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(include_email=True),
        'access_token': access_token,
        'refresh_token': refresh_token
    })

@app.route('/api/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
@handle_errors
def refresh():
    """Refresh access token using refresh token."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'Invalid user'}), 401
    
    access_token = create_access_token(identity=user_id)
    return jsonify({'access_token': access_token})

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
@handle_errors
def logout():
    """Logout user by revoking current token."""
    jti = get_jwt()['jti']
    token_blocklist.add(jti)
    logger.info(f"User logged out, token revoked: {jti[:8]}...")
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
@handle_errors
def get_current_user():
    """Get current authenticated user info."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': user.to_dict(include_email=True)})

@app.route('/api/auth/me', methods=['PUT'])
@jwt_required()
@handle_errors
def update_current_user():
    """Update current user's profile."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    if 'email' in data:
        email = data['email'].strip().lower()
        if email != user.email:
            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'Email already in use'}), 409
            user.email = email
    
    if 'current_password' in data and 'new_password' in data:
        if not user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 400
        if len(data['new_password']) < 8:
            return jsonify({'error': 'New password must be at least 8 characters'}), 400
        user.set_password(data['new_password'])
    
    db.session.commit()
    return jsonify({'user': user.to_dict(include_email=True), 'message': 'Profile updated'})

@app.route('/api/auth/request-reset', methods=['POST'])
@handle_errors
def request_password_reset():
    """Request a password reset token (would normally send email)."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    # Always return success to prevent email enumeration
    if user:
        token = user.generate_reset_token()
        db.session.commit()
        # In production, send email here
        logger.info(f"Password reset requested for: {email}, token: {token[:8]}...")
        # For demo purposes, include token in response
        return jsonify({
            'message': 'If an account exists with this email, a reset link has been sent',
            'reset_token': token  # Remove this in production!
        })
    
    return jsonify({'message': 'If an account exists with this email, a reset link has been sent'})

@app.route('/api/auth/reset-password', methods=['POST'])
@handle_errors
def reset_password():
    """Reset password using reset token."""
    data = request.get_json()
    token = data.get('token', '')
    new_password = data.get('password', '')
    
    if not token or not new_password:
        return jsonify({'error': 'Token and new password required'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        return jsonify({'error': 'Invalid or expired reset token'}), 400
    
    user.set_password(new_password)
    user.clear_reset_token()
    db.session.commit()
    
    logger.info(f"Password reset completed for: {user.username}")
    return jsonify({'message': 'Password reset successful'})

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
@handle_errors
def admin_list_users():
    """List all users (admin only)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    search = request.args.get('search', '').strip()
    
    query = User.query.order_by(User.created_at.desc())
    
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'users': [u.to_dict(include_email=True) for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_required
@handle_errors
def admin_get_user(user_id):
    """Get specific user details (admin only)."""
    user = User.query.get_or_404(user_id)
    return jsonify({'user': user.to_dict(include_email=True)})

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
@handle_errors
def admin_update_user(user_id):
    """Update user (admin only)."""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    current_user_id = get_jwt_identity()
    
    if 'is_admin' in data:
        # Prevent removing own admin status
        if user_id == current_user_id and not data['is_admin']:
            return jsonify({'error': 'Cannot remove your own admin status'}), 400
        user.is_admin = bool(data['is_admin'])
    
    if 'is_active' in data:
        # Prevent deactivating own account
        if user_id == current_user_id and not data['is_active']:
            return jsonify({'error': 'Cannot deactivate your own account'}), 400
        user.is_active = bool(data['is_active'])
    
    if 'email' in data:
        email = data['email'].strip().lower()
        if email != user.email:
            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'Email already in use'}), 409
            user.email = email
    
    if 'password' in data and data['password']:
        if len(data['password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        user.set_password(data['password'])
    
    db.session.commit()
    logger.info(f"Admin updated user: {user.username}")
    return jsonify({'user': user.to_dict(include_email=True), 'message': 'User updated'})

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
@handle_errors
def admin_delete_user(user_id):
    """Delete user (admin only)."""
    user = User.query.get_or_404(user_id)
    current_user_id = get_jwt_identity()
    
    if user_id == current_user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    logger.info(f"Admin deleted user: {user.username}")
    return jsonify({'message': 'User deleted'})

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
@handle_errors
def admin_stats():
    """Get admin dashboard statistics."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(is_admin=True).count()
    
    # Users registered in last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_users = User.query.filter(User.created_at >= week_ago).count()
    
    # Users logged in last 24 hours
    day_ago = datetime.utcnow() - timedelta(days=1)
    recent_logins = User.query.filter(User.last_login >= day_ago).count()
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'admin_users': admin_users,
        'new_users_7d': new_users,
        'recent_logins_24h': recent_logins
    })

# ============================================================================
# HEALTH & SETUP
# ============================================================================

@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'backend', 'auth': 'enabled'})

def setup_app(app):
    """Initialize app configuration and database."""
    db.init_app(app)
    jwt.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # Auto-seed admin user if none exists
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True,
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin user created: admin / admin123")
        
        logger.info("Database initialized with auth system")

# Initialize
setup_app(app)

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
    app.run(host='0.0.0.0', port=port)
