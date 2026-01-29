import sys, os
sys.path.insert(0, '/app/src')
from app.factory import create_app
from app.models import User
from app.extensions import db
app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@thesis.local', full_name='System Administrator')
    admin.set_password('admin123')
    admin.is_admin = True
    admin.is_active = True
    db.session.add(admin)
    db.session.commit()
    print('ADMIN_CREATED')
