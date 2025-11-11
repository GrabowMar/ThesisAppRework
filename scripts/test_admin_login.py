#!/usr/bin/env python3
"""Test admin user login credentials."""

import sys
from pathlib import Path

# Add src directory to Python path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import User

def main():
    app = create_app()
    
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            print(f"✅ Admin user found: {admin.username}")
            print(f"   Email: {admin.email}")
            print(f"   Is admin: {admin.is_admin}")
            print(f"   Is active: {admin.is_active}")
            
            # Test the password
            test_password = "ia5aeQE2wR87J8w"
            if admin.check_password(test_password):
                print(f"✅ Password verification SUCCESS for: {test_password}")
            else:
                print(f"❌ Password verification FAILED for: {test_password}")
        else:
            print("❌ Admin user not found!")

if __name__ == '__main__':
    main()
