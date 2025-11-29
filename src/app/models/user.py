"""
User Model for Authentication
==============================

Handles user accounts, authentication, and authorization.
"""

from datetime import datetime, timezone
from typing import Optional
import secrets
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class User(UserMixin, db.Model):
    """
    User model for authentication.
    
    Stores user credentials and metadata for the application's authentication system.
    Uses Flask-Login's UserMixin for session management.
    """
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # User metadata
    full_name = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # API Access
    api_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    api_token_created_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    
    def __init__(self, username: str, email: str, full_name: Optional[str] = None):
        """Initialize a new user."""
        self.username = username
        self.email = email
        self.full_name = full_name
    
    def set_password(self, password: str) -> None:
        """
        Hash and store a password.
        
        Args:
            password: Plain text password to hash
        """
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.
        
        Args:
            password: Plain text password to verify
            
        Returns:
            True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login = datetime.now(timezone.utc)
        db.session.commit()
    
    def generate_api_token(self) -> str:
        """Generate a new API token for this user."""
        self.api_token = secrets.token_urlsafe(48)
        self.api_token_created_at = datetime.now(timezone.utc)
        db.session.commit()
        return self.api_token
    
    def revoke_api_token(self) -> None:
        """Revoke the current API token."""
        self.api_token = None
        self.api_token_created_at = None
        db.session.commit()
    
    @staticmethod
    def verify_api_token(token: str) -> Optional['User']:
        """Verify an API token and return the associated user."""
        if not token:
            return None
        return User.query.filter_by(api_token=token, is_active=True).first()
    
    def __repr__(self) -> str:
        return f'<User {self.username}>'
    
    def to_dict(self, include_token: bool = False) -> dict:
        """Convert user to dictionary (excluding password hash)."""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'has_api_token': self.api_token is not None,
        }
        if include_token and self.api_token:
            data['api_token'] = self.api_token
            data['api_token_created_at'] = self.api_token_created_at.isoformat() if self.api_token_created_at else None
        return data
