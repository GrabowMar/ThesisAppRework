#!/usr/bin/env python
"""Create admin user for the application."""
import sys
from app.factory import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    # Check if admin exists
    admin = User.query.filter_by(username='admin').first()
    
    if admin:
        print("Admin user already exists. Updating password...")
        admin.set_password('admin123')
        db.session.commit()
        print("✅ Admin password updated to: admin123")
    else:
        print("Creating new admin user...")
        admin = User(
            username='admin',
            email='admin@thesis.local',
            full_name='Administrator',
            is_admin=True,
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created!")
        print("   Username: admin")
        print("   Password: admin123")
