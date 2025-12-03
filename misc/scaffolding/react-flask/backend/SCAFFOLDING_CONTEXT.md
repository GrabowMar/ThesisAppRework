# Backend Blueprint Reference

## Stack
- **Flask 3.0** (Python 3.11)
- **SQLAlchemy** with SQLite (`/app/data/app.db`)
- **Flask-CORS** enabled
- **Gunicorn** (production) / Werkzeug (dev)

## Architecture Rules
1. ALL API routes start with `/api/`
2. Models inherit from `db.Model` and have `to_dict()` method
3. Database path: `sqlite:////app/data/app.db`
4. Port from `FLASK_RUN_PORT` env (default 5000)
5. Host must be `0.0.0.0` for container access

## Patterns

### Model Definition
```python
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

### CRUD Routes
```python
@app.route('/api/items', methods=['GET'])
def get_items():
    items = Item.query.all()
    return jsonify([i.to_dict() for i in items])

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    item = Item(name=data['name'])
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201

@app.route('/api/items/<int:id>', methods=['PUT'])
def update_item(id):
    item = Item.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data:
        item.name = data['name']
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/items/<int:id>', methods=['DELETE'])
def delete_item(id):
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Deleted'})
```

### Pagination
```python
@app.route('/api/items')
def get_items():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    pagination = Item.query.paginate(page=page, per_page=per_page)
    return jsonify({
        'items': [i.to_dict() for i in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })
```

### Error Handling
```python
from functools import wraps

def handle_errors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error: {e}")
            return jsonify({'error': 'Server error'}), 500
    return decorated
```

### Auth (if requirements need it)
```python
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import bcrypt

app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'secret')
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password', '')):
        return jsonify({'token': create_access_token(identity=user.id)})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/protected')
@jwt_required()
def protected():
    user_id = get_jwt_identity()
    return jsonify({'user_id': user_id})
```

## Available Imports
```python
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import os, logging, secrets
# If auth needed: flask_jwt_extended, bcrypt
```
