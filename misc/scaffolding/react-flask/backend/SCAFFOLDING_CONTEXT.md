```markdown
# Backend Blueprint Reference

## CRITICAL RULES (READ FIRST)
1. **Use EXACT endpoint paths from requirements** - Replace `/api/YOUR_RESOURCE` with actual paths like `/api/todos`, `/api/books`
2. **Database path**: Use exactly `sqlite:////app/data/app.db` (4 slashes for absolute path)
3. **Define helpers BEFORE using them**: Put decorators and validators at TOP, before routes
4. **Write production-ready code**: Include thorough validation, meaningful error messages, and proper logging

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
import os, logging, re

# 2. App setup with configuration
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'  # 4 slashes!
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False
db = SQLAlchemy(app)
CORS(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 3. Validation helpers (MUST BE BEFORE ROUTES)
class ValidationError(Exception):
    """Custom validation error with field-specific messages"""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)

def validate_required(data, fields):
    """Validate that required fields are present and non-empty"""
    errors = {}
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field] = f'{field.replace("_", " ").title()} is required'
    if errors:
        raise ValidationError('Validation failed', errors)
    return True

def validate_length(value, field_name, min_len=1, max_len=500):
    """Validate string length within bounds"""
    if value and len(str(value)) < min_len:
        raise ValidationError(f'{field_name} must be at least {min_len} characters', field_name)
    if value and len(str(value)) > max_len:
        raise ValidationError(f'{field_name} must be at most {max_len} characters', field_name)
    return True

def validate_email(email):
    """Validate email format if email field is used"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if email and not re.match(pattern, email):
        raise ValidationError('Invalid email format', 'email')
    return True

# 4. Error handling decorator
def handle_errors(f):
    """Wrap route handlers with consistent error handling"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error: {e.message}")
            return jsonify({'error': e.message, 'field': e.field}), 400
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500
    return decorated

# 5. Models - RENAME to match your requirements (Todo, Book, Task, etc.)
class YourModel(db.Model):  # <- RENAME THIS (e.g., Todo, Book, Task)
    """Database model - add docstring describing the entity"""
    __tablename__ = 'your_resources'  # <- RENAME to match resource
    
    id = db.Column(db.Integer, primary_key=True)
    # Add fields from requirements with proper constraints:
    # title = db.Column(db.String(200), nullable=False)
    # description = db.Column(db.Text, nullable=True)
    # completed = db.Column(db.Boolean, default=False, nullable=False)
    # priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Serialize model to dictionary for JSON response"""
        return {
            'id': self.id,
            # Return all model fields here
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<YourModel {self.id}>'

# 6. Create tables
with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully")

# 7. Routes - USE EXACT PATHS FROM REQUIREMENTS
@app.route('/api/health')
def health():
    """Health check endpoint for container orchestration"""
    return jsonify({
        'status': 'healthy',
        'service': 'backend',
        'timestamp': datetime.utcnow().isoformat()
    })

# REPLACE '/api/YOUR_RESOURCE' with actual path from requirements!
@app.route('/api/YOUR_RESOURCE', methods=['GET'])
@handle_errors
def get_resources():
    """List all resources with optional filtering and sorting"""
    # Query parameters for filtering
    sort_by = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')
    
    # Build query with sorting
    query = YourModel.query
    if hasattr(YourModel, sort_by):
        sort_column = getattr(YourModel, sort_by)
        query = query.order_by(sort_column.desc() if order == 'desc' else sort_column.asc())
    
    resources = query.all()
    logger.info(f"Retrieved {len(resources)} resources")
    return jsonify({
        'items': [r.to_dict() for r in resources],
        'total': len(resources)
    })

@app.route('/api/YOUR_RESOURCE', methods=['POST'])
@handle_errors
def create_resource():
    """Create a new resource with validation"""
    data = request.get_json()
    if not data:
        raise ValidationError('Request body is required')
    
    # Validate required fields - adjust based on your model
    validate_required(data, ['title'])  # <- Add your required fields
    validate_length(data.get('title'), 'Title', min_len=1, max_len=200)
    
    # Create and save resource
    resource = YourModel(
        # Map fields from request data
        # title=data['title'].strip(),
        # description=data.get('description', '').strip() or None,
    )
    db.session.add(resource)
    db.session.commit()
    
    logger.info(f"Created resource with id {resource.id}")
    return jsonify(resource.to_dict()), 201

@app.route('/api/YOUR_RESOURCE/<int:id>', methods=['GET'])
@handle_errors
def get_resource(id):
    """Get a single resource by ID"""
    resource = YourModel.query.get_or_404(id, description=f'Resource with id {id} not found')
    return jsonify(resource.to_dict())

@app.route('/api/YOUR_RESOURCE/<int:id>', methods=['PUT'])
@handle_errors
def update_resource(id):
    """Update an existing resource"""
    resource = YourModel.query.get_or_404(id, description=f'Resource with id {id} not found')
    data = request.get_json()
    
    if not data:
        raise ValidationError('Request body is required')
    
    # Update fields if provided - adjust based on your model
    # if 'title' in data:
    #     validate_length(data['title'], 'Title', min_len=1, max_len=200)
    #     resource.title = data['title'].strip()
    # if 'description' in data:
    #     resource.description = data['description'].strip() or None
    # if 'completed' in data:
    #     resource.completed = bool(data['completed'])
    
    db.session.commit()
    logger.info(f"Updated resource {id}")
    return jsonify(resource.to_dict())

@app.route('/api/YOUR_RESOURCE/<int:id>', methods=['DELETE'])
@handle_errors
def delete_resource(id):
    """Delete a resource by ID"""
    resource = YourModel.query.get_or_404(id, description=f'Resource with id {id} not found')
    db.session.delete(resource)
    db.session.commit()
    logger.info(f"Deleted resource {id}")
    return jsonify({'message': 'Successfully deleted', 'id': id})

# 8. Error handlers for common HTTP errors
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# 9. Main
if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
```

## Response Formats
- **List**: `{"items": [...], "total": N}`
- **Single**: `{...item fields...}`
- **Created**: `{...item fields...}` with status 201
- **Updated**: `{...item fields...}`
- **Deleted**: `{"message": "Successfully deleted", "id": N}`
- **Validation Error**: `{"error": "message", "field": "field_name"}` with status 400
- **Not Found**: `{"error": "Resource not found"}` with status 404
- **Server Error**: `{"error": "Internal server error"}` with status 500

## Quality Checklist
- [ ] All fields from requirements are in the model
- [ ] Required fields have validation
- [ ] String fields have length limits
- [ ] Meaningful error messages for each validation
- [ ] Logging for important operations
- [ ] Proper HTTP status codes
```
