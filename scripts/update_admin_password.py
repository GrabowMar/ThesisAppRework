#!/usr/bin/env python
"""
Update Admin Password
====================

Updates the password for the admin user with a secure password.
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import User


def update_admin_password(username: str, new_password: str):
    """Update admin user password."""
    app = create_app()
    
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"❌ User '{username}' not found!")
            return False
        
        user.set_password(new_password)
        db.session.commit()
        
        print(f"✅ Password updated for user '{username}'")
        return True


if __name__ == '__main__':
    import os

    # Check for environment-based update
    admin_user = os.environ.get('ADMIN_USERNAME')
    admin_pass = os.environ.get('ADMIN_PASSWORD')

    if admin_user and admin_pass:
        print("Found admin credentials in environment variables. Updating password...")
        success = update_admin_password(admin_user, admin_pass)
        sys.exit(0 if success else 1)
    
    if len(sys.argv) > 2:
        # Command line mode: python update_admin_password.py <username> <password>
        username = sys.argv[1]
        password = sys.argv[2]
        success = update_admin_password(username, password)
        sys.exit(0 if success else 1)

    print("Please provide credentials via environment variables (ADMIN_USERNAME, ADMIN_PASSWORD) or command-line arguments.")
    sys.exit(1)

