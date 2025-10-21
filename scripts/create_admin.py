#!/usr/bin/env python
"""
Create Admin User Script
========================

Creates an admin user for the application.
Usage: python create_admin.py
"""

import os
import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import User


def create_admin_user(username: str, email: str, password: str, full_name: str = None):
    """
    Create an admin user.
    
    Args:
        username: Admin username
        email: Admin email
        password: Admin password
        full_name: Admin full name (optional)
    """
    app = create_app()
    
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"❌ User '{username}' already exists!")
            return False
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            print(f"❌ Email '{email}' is already registered!")
            return False
        
        # Create new admin user
        admin = User(
            username=username,
            email=email,
            full_name=full_name or "Administrator"
        )
        admin.set_password(password)
        admin.is_admin = True
        admin.is_active = True
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"✅ Admin user '{username}' created successfully!")
        print(f"   Email: {email}")
        print(f"   Admin: Yes")
        return True


def interactive_create():
    """Interactive admin user creation."""
    print("=" * 60)
    print("Create Admin User for AI Analysis Platform")
    print("=" * 60)
    print()
    
    # Get user input
    username = input("Username: ").strip()
    if not username:
        print("❌ Username is required!")
        return False
    
    email = input("Email: ").strip()
    if not email:
        print("❌ Email is required!")
        return False
    
    full_name = input("Full Name (optional): ").strip()
    
    # Get password with confirmation
    import getpass
    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm Password: ")
    
    if password != password_confirm:
        print("❌ Passwords do not match!")
        return False
    
    if len(password) < 8:
        print("❌ Password must be at least 8 characters!")
        return False
    
    print()
    print("Creating admin user...")
    return create_admin_user(username, email, password, full_name or None)


if __name__ == '__main__':
    # Check for environment-based quick creation
    if len(sys.argv) > 1:
        # Usage: python create_admin.py <username> <email> <password> [full_name]
        if len(sys.argv) < 4:
            print("Usage: python create_admin.py <username> <email> <password> [full_name]")
            print("   Or: python create_admin.py (for interactive mode)")
            sys.exit(1)
        
        username = sys.argv[1]
        email = sys.argv[2]
        password = sys.argv[3]
        full_name = sys.argv[4] if len(sys.argv) > 4 else None
        
        success = create_admin_user(username, email, password, full_name)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        success = interactive_create()
        sys.exit(0 if success else 1)
