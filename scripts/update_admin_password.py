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
    import getpass
    
    if len(sys.argv) > 2:
        # Command line mode: python update_admin_password.py <username> <password>
        username = sys.argv[1]
        password = sys.argv[2]
    else:
        # Interactive mode
        print("=" * 60)
        print("Update Admin Password")
        print("=" * 60)
        print()
        
        username = input("Username: ").strip() or "admin"
        password = getpass.getpass("New Password: ")
        password_confirm = getpass.getpass("Confirm Password: ")
        
        if password != password_confirm:
            print("❌ Passwords do not match!")
            sys.exit(1)
        
        if len(password) < 8:
            print("❌ Password must be at least 8 characters!")
            sys.exit(1)
    
    success = update_admin_password(username, password)
    sys.exit(0 if success else 1)
