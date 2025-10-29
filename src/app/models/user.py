"""
User Models
===========

User authentication and authorization models.
"""

from datetime import datetime, timezone
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(db.String(80), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(db.String(200), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    
    # API token fields
    api_token: Mapped[Optional[str]] = mapped_column(db.String(100), unique=True, nullable=True, index=True)
    api_token_created_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    def set_password(self, password: str):
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check if password matches hash."""
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login_at = datetime.now(timezone.utc)
    
    def __repr__(self):
        return f"<User {self.username}>"
