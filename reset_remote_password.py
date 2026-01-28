import sys
import os
sys.path.append('/app/src')

from app.factory import create_app
from app.extensions import db
from app.models import User

def reset():
    app = create_app()
    with app.app_context():
        u = User.query.filter_by(username='admin').first()
        if not u:
            print("User 'admin' not found. Creating...")
            u = User(
                username='admin',
                email='admin@thesis.local',
                full_name='System Administrator'
            )
            u.is_admin = True
            u.is_active = True
            db.session.add(u)
        
        u.set_password('admin123')
        db.session.commit()
        print("SUCCESS: Password set to 'admin123'")

if __name__ == "__main__":
    reset()
