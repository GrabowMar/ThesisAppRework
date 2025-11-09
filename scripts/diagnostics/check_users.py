"""Quick script to check users in the database."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    users = User.query.all()
    print(f'Total users: {len(users)}')
    for u in users:
        print(f'- Username: {u.username}, Active: {u.is_active}, Email: {u.email}')
    
    if len(users) == 0:
        print('\nNo users found. Creating default admin user...')
        admin = User(
            username='admin',
            email='admin@example.com',
            full_name='Administrator'
        )
        admin.set_password('admin123')
        admin.is_active = True
        db.session.add(admin)
        db.session.commit()
        print('✓ Created admin user (username: admin, password: admin123)')
