"""
Authentication System for AI Testing Framework
===========================================

User authentication and session management with Flask-Login.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from .extensions import db
    from .constants import JobStatus, TaskStatus
except ImportError:
    from extensions import db
    from constants import JobStatus, TaskStatus


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # User profile
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), default='user', nullable=False)  # user, admin, researcher
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    
    # Authentication tracking
    last_login = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, default=0)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    
    # API access
    api_key = db.Column(db.String(64), unique=True, index=True)
    api_requests_count = db.Column(db.Integer, default=0)
    api_requests_last_reset = db.Column(db.DateTime, default=utc_now)
    
    # Preferences
    preferences_json = db.Column(db.Text)  # JSON field for user preferences
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    
    # Relationships - foreign keys added to existing models
    # Note: These will be added via migration to existing models:
    # SecurityAnalysis.created_by -> User.id
    # PerformanceTest.created_by -> User.id
    # BatchJob.created_by -> User.id
    # ZAPAnalysis.created_by -> User.id
    # OpenRouterAnalysis.created_by -> User.id
    
    def __init__(self, username: str, email: str, password: str, **kwargs):
        """Initialize user with required fields."""
        self.username = username
        self.email = email
        self.set_password(password)
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Generate API key
        self.generate_api_key()
    
    def set_password(self, password: str) -> None:
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def generate_api_key(self) -> str:
        """Generate a new API key."""
        import secrets
        self.api_key = secrets.token_urlsafe(32)
        return self.api_key
    
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == 'admin'
    

    
    def can_create_batch_jobs(self) -> bool:
        """Check if user can create batch jobs."""
        return self.role in ['researcher', 'admin']
    
    def can_access_api(self) -> bool:
        """Check if user can access API."""
        return self.is_active and self.api_key is not None
    
    def record_login(self) -> None:
        """Record successful login."""
        self.last_login = utc_now()
        self.login_count += 1
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def record_failed_login(self) -> None:
        """Record failed login attempt."""
        self.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = utc_now() + timedelta(minutes=30)
    
    def is_locked(self) -> bool:
        """Check if account is locked."""
        if self.locked_until is None:
            return False
        return utc_now() < self.locked_until
    

    
    def get_api_rate_limit(self) -> int:
        """Get daily API rate limit based on role."""
        limits = {
            'user': 100,
            'researcher': 1000,
            'admin': 10000
        }
        return limits.get(self.role, 100)
    

    
    def get_preferences(self) -> dict:
        """Get user preferences."""
        if not self.preferences_json:
            return {}
        
        import json
        try:
            return json.loads(self.preferences_json)
        except json.JSONDecodeError:
            return {}
    

    
    def get_full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username
    
    def get_display_name(self) -> str:
        """Get display name for UI."""
        full_name = self.get_full_name()
        if full_name != self.username:
            return f"{full_name} ({self.username})"
        return self.username
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert user to dictionary."""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email if include_sensitive else '***',
            'full_name': self.get_full_name(),
            'display_name': self.get_display_name(),
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'login_count': self.login_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        
        if include_sensitive:
            data.update({
                'api_key': self.api_key,
                'api_requests_count': self.api_requests_count,
                'api_rate_limit': self.get_api_rate_limit(),
                'failed_login_attempts': self.failed_login_attempts,
                'is_locked': self.is_locked(),
                'preferences': self.get_preferences()
            })
        
        return data
    
    def __repr__(self) -> str:
        return f'<User {self.username}>'


class SessionToken(db.Model):
    """Session tokens for API authentication."""
    __tablename__ = 'session_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100))  # User-friendly name for the token
    expires_at = db.Column(db.DateTime, nullable=False)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Token permissions
    can_read = db.Column(db.Boolean, default=True, nullable=False)
    can_write = db.Column(db.Boolean, default=False, nullable=False)
    can_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('session_tokens', lazy=True, cascade='all, delete-orphan'))
    
    def __init__(self, user_id: int, name: str = None, expires_days: int = 30, **permissions):
        """Initialize session token."""
        self.user_id = user_id
        self.name = name or f"Token {datetime.now().strftime('%Y-%m-%d')}"
        
        # Set expiration
        from datetime import timedelta
        self.expires_at = utc_now() + timedelta(days=expires_days)
        
        # Set permissions
        for perm, value in permissions.items():
            if hasattr(self, perm):
                setattr(self, perm, value)
        
        # Generate token
        self.generate_token()
    
    def generate_token(self) -> str:
        """Generate secure token."""
        import secrets
        self.token = secrets.token_urlsafe(64)
        return self.token
    
    def is_valid(self) -> bool:
        """Check if token is valid."""
        if not self.is_active:
            return False
        if utc_now() > self.expires_at:
            return False
        return True
    
    def record_usage(self) -> None:
        """Record token usage."""
        self.last_used = utc_now()
    
    def revoke(self) -> None:
        """Revoke the token."""
        self.is_active = False
    
    def to_dict(self, include_token: bool = False) -> dict:
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'expires_at': self.expires_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'is_active': self.is_active,
            'is_valid': self.is_valid(),
            'permissions': {
                'can_read': self.can_read,
                'can_write': self.can_write,
                'can_admin': self.can_admin
            },
            'created_at': self.created_at.isoformat()
        }
        
        if include_token:
            data['token'] = self.token
        
        return data
    
    def __repr__(self) -> str:
        return f'<SessionToken {self.name} for User {self.user_id}>'


def create_default_admin() -> Optional[User]:
    """Create default admin user if none exists."""
    try:
        # Check if any admin exists
        existing_admin = User.query.filter_by(role='admin').first()
        if existing_admin:
            return existing_admin
        
        # Create default admin
        admin_username = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
        admin_email = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@localhost')
        admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
        
        admin = User(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            role='admin',
            first_name='System',
            last_name='Administrator',
            is_verified=True
        )
        
        db.session.add(admin)
        db.session.commit()
        
        current_app.logger.info(f"Created default admin user: {admin_username}")
        return admin
        
    except Exception as e:
        current_app.logger.error(f"Failed to create default admin: {e}")
        db.session.rollback()
        return None



