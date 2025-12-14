````markdown
# Backend Context

## Architecture (4-Query System)
```
backend/
├── app.py          # Entry point (DO NOT MODIFY)
├── models.py       # SQLAlchemy models (Query 1) - User model pre-built
├── services.py     # Business logic (Query 1)
└── routes/
    ├── __init__.py # Blueprints setup (DO NOT MODIFY)
    ├── auth.py     # Authentication routes (PRE-BUILT - DO NOT MODIFY)
    ├── user.py     # User API endpoints (Query 1)
    └── admin.py    # Admin API endpoints (Query 2)
```

## Environment
- DB: `sqlite:////app/data/app.db` (4 slashes)
- Uploads: `/app/data/uploads`
- Port: env `FLASK_RUN_PORT` or 5000
- Default admin: `admin` / `admin2025` (from .env)

## Stack
Flask 3.0, Flask-CORS, SQLAlchemy, gunicorn, bcrypt, PyJWT, werkzeug

## Authentication (PRE-BUILT)
The app includes a complete JWT-based auth system:

### User Model (already in models.py)
```python
class User(db.Model):
    id, username, email, password_hash, is_admin, is_active, created_at, last_login
    
    def set_password(password)  # Hash with bcrypt
    def check_password(password)  # Verify password
    def to_dict()  # Safe serialization (no password_hash)
```

### Auth Endpoints (routes/auth.py - DO NOT MODIFY)
- `POST /api/auth/register` - Register new user, returns JWT
- `POST /api/auth/login` - Login, returns JWT token
- `GET /api/auth/me` - Get current user (requires token)
- `POST /api/auth/logout` - Logout (client clears token)
- `POST /api/auth/change-password` - Change password

### Protecting Routes
```python
from routes.auth import token_required, admin_required

# Any authenticated user
@user_bp.route('/protected')
@token_required
def protected_route(current_user):
    return jsonify({'user': current_user.username})

# Admin only
@admin_bp.route('/admin-only')
@admin_required
def admin_route(current_user):
    return jsonify({'admin': current_user.username})
```

## Rules
1. Keep `/api/health` → `{"status": "healthy"}` (in app.py)
2. User routes under `/api/` (user_bp)
3. Admin routes under `/api/admin/` (admin_bp)
4. Auth routes under `/api/auth/` (auth_bp) - pre-built
5. Models MUST have `to_dict()` method
6. Use `host='0.0.0.0'` in `app.run()` for Docker
7. Use `@token_required` or `@admin_required` for protected routes

## Patterns (Pseudocode)

### Models (models.py)
```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# User model is pre-built - just add your models below it

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # For soft delete
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Optional owner
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

### User Routes (routes/user.py)
```python
from flask import jsonify, request
from routes import user_bp
from routes.auth import token_required  # For protected routes
from models import db, Item

@user_bp.route('/items', methods=['GET'])
def get_items():
    items = Item.query.filter_by(is_active=True).all()
    return jsonify([i.to_dict() for i in items])

@user_bp.route('/items', methods=['POST'])
@token_required  # Require authentication to create
def create_item(current_user):
    data = request.get_json()
    item = Item(name=data['name'], user_id=current_user.id)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201
```

### Admin Routes (routes/admin.py)
```python
from flask import jsonify, request
from routes import admin_bp
from routes.auth import admin_required
from models import db, Item

@admin_bp.route('/items', methods=['GET'])
@admin_required
def admin_get_all(current_user):
    items = Item.query.all()  # ALL including inactive
    return jsonify([i.to_dict() for i in items])

@admin_bp.route('/items/<int:id>/toggle', methods=['POST'])
@admin_required
def toggle_status(current_user, id):
    item = Item.query.get_or_404(id)
    item.is_active = not item.is_active
    db.session.commit()
    return jsonify(item.to_dict())

@admin_bp.route('/items/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete(current_user):
    ids = request.get_json().get('ids', [])
    Item.query.filter(Item.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'deleted': len(ids)})

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats(current_user):
    return jsonify({
        'total': Item.query.count(),
        'active': Item.query.filter_by(is_active=True).count()
    })
```

## Gotchas
- Flask 3.0: NO `@app.before_first_request`
- `get_or_404()` auto-returns 404
- Rollback on errors
- Import models: `from models import db, ModelName`
- Blueprints already have prefixes set
- Protected routes: decorator passes `current_user` as first arg
- Default admin user created on startup (admin/admin2025)

````
