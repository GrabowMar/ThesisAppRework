import sys, os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.models import User
from app.extensions import db

def main():
    if len(sys.argv) < 2:
        print("Usage: python create_admin.py <password>")
        sys.exit(1)
        
    password = sys.argv[1]
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin', 
                email='admin@thesis.local', 
                full_name='System Administrator'
            )
            admin.set_password(password)
            admin.is_admin = True
            admin.is_active = True
            db.session.add(admin)
            print('CREATED')
        else:
            admin.set_password(password)
            print('UPDATED')
        db.session.commit()

if __name__ == '__main__':
    main()
