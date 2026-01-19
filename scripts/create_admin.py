#!/usr/bin/env python
"""
Create Admin User
=================

This script creates or updates the admin user account in the database.

The script will:
1. Check if an admin user already exists
2. Create a new admin user if none exists, or reset the password if it does
3. Set admin privileges and default credentials

Default Credentials:
- Username: admin
- Password: admin2025
- Email: admin@thesis-app.local

Usage:
    python scripts/create_admin.py

Note: This script is intended for development and initial setup only.
In production environments, admin accounts should be created through
proper user management interfaces with secure password policies.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.extensions import db
from app.models.user import User

def main():
    app = create_app()
    with app.app_context():
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print(f'Admin user already exists (id={admin.id})')
            # Reset password anyway
            admin.set_password('admin2025')
            admin.is_admin = True
            db.session.commit()
            print('Password has been reset to: admin2025')
        else:
            # Create admin user - note: is_admin must be set after creation
            admin = User(
                username='admin',
                email='admin@thesis-app.local',
            )
            admin.set_password('admin2025')
            admin.is_admin = True
            db.session.add(admin)
            db.session.commit()
            print('Admin user created successfully!')
        
        print()
        print('=' * 40)
        print('Admin Login Credentials:')
        print('=' * 40)
        print('  Username: admin')
        print('  Password: admin2025')
        print('  Email: admin@thesis-app.local')
        print('=' * 40)

if __name__ == '__main__':
    main()
