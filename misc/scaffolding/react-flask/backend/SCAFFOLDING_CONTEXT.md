# Backend Scaffolding Context

## Technical Stack
- **Framework**: Flask 3.0 (Python 3.11)
- **Database**: SQLAlchemy with SQLite (`/app/data/app.db`)
- **CORS**: Flask-CORS enabled for all routes
- **Authentication**: Flask-JWT-Extended with bcrypt password hashing
- **Server**: Gunicorn (production) / Werkzeug (dev)
- **Validation**: Manual validation with proper error responses

## ⚡ BUILT-IN AUTHENTICATION SYSTEM

The scaffolding includes a complete auth system. **Do NOT recreate auth** - extend it!

### Pre-built Auth Endpoints
- `POST /api/auth/register` - User registration (auto-login after)
- `POST /api/auth/login` - Login with username/email + password
- `POST /api/auth/logout` - Logout (revokes token)
- `POST /api/auth/refresh` - Refresh access token
- `GET /api/auth/me` - Get current user info
- `PUT /api/auth/me` - Update profile (email, password)
- `POST /api/auth/request-reset` - Request password reset
- `POST /api/auth/reset-password` - Reset password with token

### Pre-built Admin Endpoints
- `GET /api/admin/users` - List all users (paginated, searchable)
- `GET /api/admin/users/<id>` - Get user details
- `PUT /api/admin/users/<id>` - Update user (admin/active status, email, password)
- `DELETE /api/admin/users/<id>` - Delete user
- `GET /api/admin/stats` - Dashboard statistics

### Default Admin User
On first run, an admin user is auto-created:
- **Username**: `admin`
- **Password**: `admin123`
- **Email**: `admin@example.com`

### User Model (Already Defined)
```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    
    # Methods: set_password(), check_password(), generate_reset_token(), to_dict()
```

### Using Auth Decorators

**Require authentication:**
```python
from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route('/api/items', methods=['POST'])
@jwt_required()  # User must be logged in
@handle_errors
def create_item():
    user_id = get_jwt_identity()  # Get current user's ID
    data = request.get_json()
    item = Item(name=data['name'], user_id=user_id)
    # ...
```

**Require admin:**
```python
@app.route('/api/settings', methods=['PUT'])
@admin_required  # User must be admin
@handle_errors
def update_settings():
    # Only admins can access this
    pass
```

**Require active user:**
```python
@app.route('/api/profile', methods=['GET'])
@active_user_required  # User must be active (not deactivated)
@handle_errors
def get_profile():
    pass
```

### Linking Models to Users

Add `user_id` foreign key to associate data with users:
```python
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='items')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

### User-scoped Queries
```python
@app.route('/api/items', methods=['GET'])
@jwt_required()
@handle_errors
def get_items():
    user_id = get_jwt_identity()
    items = Item.query.filter_by(user_id=user_id).all()
    return jsonify({'items': [i.to_dict() for i in items]})
```

## Architecture Constraints
1. **Entry Point**: `app.py` contains `setup_app(app)` factory function (already implemented).
2. **Routing**: ALL API routes MUST start with `/api/` (e.g., `/api/todos`).
3. **Database**:
   - Use `db = SQLAlchemy()` initialized globally (already done).
   - Models must inherit from `db.Model`.
   - Models must have a `to_dict()` method for JSON serialization.
   - Use absolute path: `sqlite:////app/data/app.db`
4. **Configuration**:
   - Port from `FLASK_RUN_PORT` env var (default 5000)
   - Host must be `0.0.0.0` for container access

## Production Patterns

### Model with to_dict() and User Association
```python
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

### Error Handling Pattern (already available)
```python
# handle_errors decorator is already defined in app.py
@app.route('/api/items', methods=['POST'])
@jwt_required()
@handle_errors
def create_item():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    # ... rest of logic
```

### Pagination Pattern
```python
@app.route('/api/items')
@jwt_required()
@handle_errors
def get_items():
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)  # Max limit
    
    query = Item.query.filter_by(user_id=user_id).order_by(Item.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'items': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })
```

### Filtering Pattern
```python
@app.route('/api/items')
@jwt_required()
@handle_errors
def get_items():
    user_id = get_jwt_identity()
    query = Item.query.filter_by(user_id=user_id)
    
    # Filter by status
    status = request.args.get('status')
    if status:
        query = query.filter(Item.status == status)
    
    # Search by name
    search = request.args.get('search')
    if search:
        query = query.filter(Item.name.ilike(f'%{search}%'))
    
    return jsonify({'items': [i.to_dict() for i in query.all()]})
```

## Complete Code Pattern (with Auth)
```python
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import os
import logging

# Note: app, db, jwt, User, handle_errors, admin_required, active_user_required
# are already defined in the scaffolding - just add your models and routes!

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# YOUR MODELS (add below the existing User model)
# ============================================================================

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'completed': self.completed,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ============================================================================
# YOUR ROUTES (add below the existing auth/admin routes)
# ============================================================================

@app.route('/api/items', methods=['GET'])
@jwt_required()
@handle_errors
def get_items():
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    query = Item.query.filter_by(user_id=user_id).order_by(Item.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'items': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@app.route('/api/items', methods=['POST'])
@jwt_required()
@handle_errors
def create_item():
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': 'Name is required'}), 400
    
    item = Item(name=data['name'].strip(), user_id=user_id)
    db.session.add(item)
    db.session.commit()
    logger.info(f"Created item: {item.id}")
    return jsonify(item.to_dict()), 201

@app.route('/api/items/<int:id>', methods=['PUT'])
@jwt_required()
@handle_errors
def update_item(id):
    user_id = get_jwt_identity()
    item = Item.query.filter_by(id=id, user_id=user_id).first_or_404()
    data = request.get_json()
    
    if 'name' in data:
        item.name = data['name'].strip()
    if 'completed' in data:
        item.completed = bool(data['completed'])
    
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/items/<int:id>', methods=['DELETE'])
@jwt_required()
@handle_errors
def delete_item(id):
    user_id = get_jwt_identity()
    item = Item.query.filter_by(id=id, user_id=user_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    logger.info(f"Deleted item: {id}")
    return jsonify({'message': 'Deleted'}), 200
```

## Quality Checklist
- [ ] All routes have `@handle_errors` decorator
- [ ] Protected routes use `@jwt_required()` or `@admin_required`
- [ ] User-specific data filtered by `user_id`
- [ ] Input validation on all POST/PUT endpoints
- [ ] Proper HTTP status codes (200, 201, 400, 401, 403, 404, 500)
- [ ] Health check endpoint at `/api/health` ✅ (built-in)
- [ ] Auth endpoints ✅ (built-in)
- [ ] Admin endpoints ✅ (built-in)
- [ ] Models have `to_dict()` method
- [ ] Logging for important operations
- [ ] Pagination for list endpoints
- [ ] CORS enabled ✅ (built-in)
