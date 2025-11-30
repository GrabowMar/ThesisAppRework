# Backend Scaffolding Context

## Technical Stack
- **Framework**: Flask 3.0 (Python 3.11)
- **Database**: SQLAlchemy with SQLite (`/app/data/app.db`)
- **CORS**: Flask-CORS enabled for all routes
- **Server**: Gunicorn (production) / Werkzeug (dev)
- **Validation**: Manual validation with proper error responses

## Architecture Constraints
1. **Entry Point**: `app.py` MUST contain a `setup_app(app)` factory function.
2. **Routing**: ALL API routes MUST start with `/api/` (e.g., `/api/todos`).
3. **Database**:
   - Use `db = SQLAlchemy()` initialized globally.
   - Models must inherit from `db.Model`.
   - Models must have a `to_dict()` method for JSON serialization.
   - Use absolute path: `sqlite:////app/data/app.db`
4. **Configuration**:
   - Port from `FLASK_RUN_PORT` env var (default 5000)
   - Host must be `0.0.0.0` for container access

## Production Patterns

### Model with to_dict()
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

### Error Handling Pattern
```python
from functools import wraps

def handle_errors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    return decorated

@app.route('/api/items', methods=['POST'])
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
def get_items():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)  # Max limit
    
    query = Item.query.order_by(Item.created_at.desc())
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
def get_items():
    query = Item.query
    
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

### Health Check (always include)
```python
@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'backend'})
```

## Complete Code Pattern
```python
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
db = SQLAlchemy()

def handle_errors(f):
    """Decorator for consistent error handling."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated

def setup_app(app):
    """Initialize app configuration and database."""
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")

# Models
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'completed': self.completed,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Routes
@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'backend'})

@app.route('/api/items', methods=['GET'])
@handle_errors
def get_items():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    query = Item.query.order_by(Item.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'items': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@app.route('/api/items', methods=['POST'])
@handle_errors
def create_item():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': 'Name is required'}), 400
    
    item = Item(name=data['name'].strip())
    db.session.add(item)
    db.session.commit()
    logger.info(f"Created item: {item.id}")
    return jsonify(item.to_dict()), 201

@app.route('/api/items/<int:id>', methods=['PUT'])
@handle_errors
def update_item(id):
    item = Item.query.get_or_404(id)
    data = request.get_json()
    
    if 'name' in data:
        item.name = data['name'].strip()
    if 'completed' in data:
        item.completed = bool(data['completed'])
    
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/items/<int:id>', methods=['DELETE'])
@handle_errors
def delete_item(id):
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    logger.info(f"Deleted item: {id}")
    return jsonify({'message': 'Deleted'}), 200

# Initialize
setup_app(app)

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

## Quality Checklist
- [ ] All routes have `@handle_errors` decorator
- [ ] Input validation on all POST/PUT endpoints
- [ ] Proper HTTP status codes (200, 201, 400, 404, 500)
- [ ] Health check endpoint at `/api/health`
- [ ] Models have `to_dict()` method
- [ ] Logging for important operations
- [ ] Pagination for list endpoints
- [ ] CORS enabled
