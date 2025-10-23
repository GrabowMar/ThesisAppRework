#!/usr/bin/env python
"""
Add New Admin User
==================

Adds a new admin user with specified credentials.
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import User


def main():
    """Create new admin user."""
    app = create_app()
    
    # Admin credentials
    username = 'admin'
    email = 'admin@thesis.local'
    password = 'ia5aeQE2wR87J8w'
    full_name = 'Administrator'
    
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"❌ User '{username}' already exists!")
            print(f"   Updating password instead...")
            existing_user.set_password(password)
            db.session.commit()
            print(f"✅ Password updated for user '{username}'")
            return
        
        # Create new admin user
        admin = User(
            username=username,
            email=email,
            full_name=full_name
        )
        admin.set_password(password)
        admin.is_admin = True
        admin.is_active = True
        
        db.session.add(admin)
        db.session.commit()
        
        print("=" * 60)
        print("✅ Admin user created successfully!")
        print("=" * 60)
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Email: {email}")
        print(f"Admin: Yes")
        print(f"Active: Yes")
        print("=" * 60)


if __name__ == '__main__':
    main()
