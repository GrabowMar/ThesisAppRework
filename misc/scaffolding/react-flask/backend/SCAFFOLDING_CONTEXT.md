# Backend Context

## Architecture (4-Query System)
```
backend/
├── app.py          # Entry point (DO NOT MODIFY)
├── models.py       # SQLAlchemy models (Query 1)
├── services.py     # Business logic (Query 1)
└── routes/
    ├── __init__.py # Blueprints setup (DO NOT MODIFY)
    ├── user.py     # User API endpoints (Query 1)
    └── admin.py    # Admin API endpoints (Query 2)
```

## Environment
- DB: `sqlite:////app/data/app.db` (4 slashes)
- Uploads: `/app/data/uploads`
- Port: env `FLASK_RUN_PORT` or 5000

## Stack
Flask 3.0, Flask-CORS, SQLAlchemy, gunicorn, bcrypt, PyJWT, werkzeug

## Rules
1. Keep `/api/health` → `{"status": "healthy"}` (in app.py)
2. User routes under `/api/` (user_bp)
3. Admin routes under `/api/admin/` (admin_bp)
4. Models MUST have `to_dict()` method
5. Use `host='0.0.0.0'` in `app.run()` for Docker

## Patterns (Pseudocode)

### Models (models.py)
```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # For soft delete
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
from models import db, Item

@user_bp.route('/items', methods=['GET'])
def get_items():
    items = Item.query.filter_by(is_active=True).all()
    return jsonify([i.to_dict() for i in items])

@user_bp.route('/items', methods=['POST'])
def create_item():
    data = request.get_json()
    item = Item(name=data['name'])
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201
```

### Admin Routes (routes/admin.py)
```python
from flask import jsonify, request
from routes import admin_bp
from models import db, Item

@admin_bp.route('/items', methods=['GET'])
def admin_get_all():
    items = Item.query.all()  # ALL including inactive
    return jsonify([i.to_dict() for i in items])

@admin_bp.route('/items/<int:id>/toggle', methods=['POST'])
def toggle_status(id):
    item = Item.query.get_or_404(id)
    item.is_active = not item.is_active
    db.session.commit()
    return jsonify(item.to_dict())

@admin_bp.route('/items/bulk-delete', methods=['POST'])
def bulk_delete():
    ids = request.get_json().get('ids', [])
    Item.query.filter(Item.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'deleted': len(ids)})

@admin_bp.route('/stats', methods=['GET'])
def get_stats():
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
