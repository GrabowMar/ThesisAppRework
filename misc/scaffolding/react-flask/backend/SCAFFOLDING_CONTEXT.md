# Backend Blueprint Reference

## CRITICAL RULES (READ FIRST)
1. **Use EXACT endpoint paths from requirements** - Replace `/api/YOUR_RESOURCE` in examples with actual paths like `/api/todos`, `/api/books`, etc.
2. **Database path**: Use exactly `sqlite:////app/data/app.db` (4 slashes for absolute path)
3. **Define helpers BEFORE using them**: Put `handle_errors` decorator definition at TOP, before routes
4. **Only implement what requirements ask for**: Do NOT add auth unless requirements specify it

## Stack
- Flask 3.0, SQLAlchemy, Flask-CORS, Gunicorn/Werkzeug

## Code Structure (FOLLOW THIS ORDER)
```python
# 1. Imports
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import os, logging

# 2. App setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'  # 4 slashes!
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 3. Helper decorators (MUST BE BEFORE ROUTES)
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

# 4. Models - RENAME to match your requirements (Todo, Book, Task, etc.)
class YourModel(db.Model):  # <- RENAME THIS (e.g., Todo, Book, Task)
    id = db.Column(db.Integer, primary_key=True)
    # Add fields from requirements (title, name, completed, etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            # Return all your model's fields here
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# 5. Create tables
with app.app_context():
    db.create_all()

# 6. Routes - USE EXACT PATHS FROM REQUIREMENTS (e.g., /api/todos, /api/books)
@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'backend'})

# REPLACE '/api/YOUR_RESOURCE' with actual path from requirements!
@app.route('/api/YOUR_RESOURCE', methods=['GET'])  # e.g., '/api/todos'
@handle_errors
def get_resources():
    resources = YourModel.query.all()
    return jsonify({'items': [r.to_dict() for r in resources], 'total': len(resources)})

@app.route('/api/YOUR_RESOURCE', methods=['POST'])  # e.g., '/api/todos'
@handle_errors
def create_resource():
    data = request.get_json()
    # Validate required fields from requirements
    resource = YourModel(**data)  # Adapt to your fields
    db.session.add(resource)
    db.session.commit()
    return jsonify(resource.to_dict()), 201

@app.route('/api/YOUR_RESOURCE/<int:id>', methods=['PUT'])  # e.g., '/api/todos/<int:id>'
@handle_errors
def update_resource(id):
    resource = YourModel.query.get_or_404(id)
    data = request.get_json()
    # Update fields from request
    db.session.commit()
    return jsonify(resource.to_dict())

@app.route('/api/YOUR_RESOURCE/<int:id>', methods=['DELETE'])  # e.g., '/api/todos/<int:id>'
@handle_errors
def delete_resource(id):
    resource = YourModel.query.get_or_404(id)
    db.session.delete(resource)
    db.session.commit()
    return jsonify({})

# 7. Main
if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

## Response Formats
- **List**: `{"items": [...], "total": N}`
- **Single**: `{...item fields...}`
- **Error**: `{"error": "message"}` with status 400/404/500
- **Delete**: `{"message": "Deleted"}` or `{}`
