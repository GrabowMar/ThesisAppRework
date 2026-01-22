#!/usr/bin/env python
"""
Wipeout Database and Initialize Admin
======================================

This script completely wipes the database and creates a fresh admin user.

Usage:
    python scripts/wipeout_and_init.py
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
        print('=' * 60)
        print('DATABASE WIPEOUT - ALL DATA WILL BE DELETED')
        print('=' * 60)
        
        # Drop all tables
        print('\n[1/3] Dropping all tables...')
        db.drop_all()
        print('✓ All tables dropped')
        
        # Recreate all tables
        print('\n[2/3] Creating fresh database schema...')
        db.create_all()
        print('✓ Database schema created')
        
        # Create admin user
        print('\n[3/3] Creating admin user...')
        admin = User(
            username='admin',
            email='admin@thesis-app.local',
        )
        admin.set_password('admin2705')
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()
        print('✓ Admin user created')
        
        print('\n' + '=' * 60)
        print('WIPEOUT COMPLETE - Database Reset Successfully')
        print('=' * 60)
        print('\nAdmin Login Credentials:')
        print('  Username: admin')
        print('  Password: admin2705')
        print('  Email: admin@thesis-app.local')
        print('=' * 60)

if __name__ == '__main__':
    main()
