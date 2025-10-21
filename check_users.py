#!/usr/bin/env python
"""Check existing users in database."""
import sys
sys.path.insert(0, 'src')

from app.extensions import db
from app.factory import create_app
from app.models import User

app = create_app()

with app.app_context():
    users = User.query.all()
    print(f'Total users: {len(users)}')
    for u in users:
        print(f'- Username: {u.username}, Email: {u.email}, Active: {u.is_active}, Admin: {u.is_admin}')
