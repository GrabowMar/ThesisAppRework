"""Comprehensive Template and System Improvements
================================================

This script applies all improvements learned from research:
1. Flask 3.0 compatibility fixes
2. Increased max_tokens for larger output
3. Few-shot examples in templates
4. Chain-of-thought prompting
5. Better scaffolding
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.paths import MISC_DIR

def update_backend_step1():
    """Update backend step 1 template with few-shot example and Flask 3.0 compatibility."""
    template_path = MISC_DIR / 'templates' / 'minimal' / 'backend_step1_structure.md.jinja2'
    
    content = '''# Task: Build Flask API for {{ name }}

{{ description }}

## Let's Think Step by Step

**Systematic Approach:**
1. Analyze requirements and plan database schema
2. Set up Flask app with proper configuration
3. Create SQLAlchemy models with timestamps
4. Implement each API endpoint with error handling

## API Requirements

{% for endpoint in endpoints %}
### {{ endpoint.method }} {{ endpoint.path }}
- **Purpose:** {{ endpoint.description }}
{% if endpoint.input %}
- **Input:** `{{ endpoint.input | tojson }}`
{% endif %}
- **Output:** `{{ endpoint.output | tojson }}`
- **Status:** 200/201 (success), 400 (invalid), 404 (not found), 500 (error)

{% endfor %}

## Technical Stack

- Flask 3.0.0 (NO deprecated @app.before_first_request!)
- SQLAlchemy + SQLite
- Flask-CORS for cross-origin

## EXAMPLE: Professional Flask 3.0 App

```python
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db = SQLAlchemy(app)

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

def validate_item(data):
    errors = []
    if not data.get('name'):
        errors.append('Name required')
    return (True, None) if not errors else (False, errors)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/api/items', methods=['GET'])
def get_items():
    try:
        items = Item.query.all()
        return jsonify([item.to_dict() for item in items]), 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/items', methods=['POST'])
def create_item():
    try:
        data = request.get_json()
        valid, errors = validate_item(data)
        if not valid:
            return jsonify({'error': errors}), 400
        
        item = Item(name=data['name'], description=data.get('description', ''))
        db.session.add(item)
        db.session.commit()
        return jsonify(item.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

# Flask 3.0 initialization (NO @app.before_first_request!)
with app.app_context():
    db.create_all()
    logger.info("Database ready")

if __name__ == '__main__':
    logger.info("Starting server...")
    app.run(host='0.0.0.0', port=5000, debug=False)
```

## Your Task

**Follow the example above to implement your API.**

### Critical Requirements:

1. **Flask 3.0 Compatible**
   - Use `with app.app_context():` for initialization
   - NO `@app.before_first_request` (removed!)

2. **Models**
   - Add `created_at`, `updated_at` to all models
   - Add `to_dict()` method for JSON

3. **Endpoints**
   - Implement ALL required endpoints
   - Wrap DB operations in try-except
   - Validate inputs before using
   - Return proper status codes

4. **Code Quality**
   - Add logging (logger.info, logger.error)
   - Create validation helpers
   - Keep code organized

## Deliverables

1. **app.py** (100-150 lines)
2. **requirements.txt**

### dependencies.txt FORMAT:

```
Flask==3.0.0
Flask-CORS==4.0.0
Flask-SQLAlchemy==3.1.1
```

**Package Mapping:**
- `from flask import ...` → `Flask==3.0.0`
- `from flask_cors import ...` → `Flask-CORS==4.0.0`
- `from flask_sqlalchemy import ...` → `Flask-SQLAlchemy==3.1.1`
- `from flask_limiter import ...` → `Flask-Limiter==3.5.0`
- `from flask_compress import ...` → `Flask-Compress==1.14`
- `import requests` → `requests==2.31.0`
- `import bcrypt` → `bcrypt==4.1.2`
- `import jwt` → `PyJWT==2.8.0`

**DO NOT import without adding to requirements.txt!**

Standard library (os, sys, json, logging, datetime, re, base64) - no need to add.

## Checklist

- ✓ Flask 3.0 compatible (with app.app_context:)
- ✓ All endpoints implemented
- ✓ Error handling (try-except)
- ✓ Input validation
- ✓ Logging
- ✗ NO @app.before_first_request
- ✗ NO missing dependencies
'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated {template_path.name}")


def update_backend_step2():
    """Update backend step 2 template."""
    template_path = MISC_DIR / 'templates' / 'minimal' / 'backend_step2_enhance.md.jinja2'
    
    content = '''# Task: Enhance {{ name }} API

Now add advanced features to make this production-ready.

## Enhancement Goals

1. **Advanced Validation**
   - Check all required fields
   - Validate data types
   - Check value ranges/formats
   - Return clear error messages

2. **Extended Features**
   - Add filtering (by multiple fields)
   - Add sorting (asc/desc)
   - Add pagination (page, per_page)
   - Add search functionality

3. **Better Error Handling**
   - Detailed error messages
   - Request tracking
   - Comprehensive logging

4. **Database Improvements**
   - Add indexes for performance
   - Add constraints (unique, not null)
   - Add relationships if needed

## Target

**Expand app.py to 200-250 lines** with:
- Enhanced validation (30-40 lines)
- Advanced query features (40-50 lines)
- Better error handling (20-30 lines)
- More endpoints (50-70 lines)

## Keep Flask 3.0 Compatible

- Still use `with app.app_context():`
- NO `@app.before_first_request`
- Add any new imports to requirements.txt
'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated {template_path.name}")


def update_backend_step3():
    """Update backend step 3 template."""
    template_path = MISC_DIR / 'templates' / 'minimal' / 'backend_step3_polish.md.jinja2'
    
    content = '''# Task: Polish {{ name }} API

Add final production features.

## Final Features

1. **Comprehensive Logging**
   - Log all operations
   - Log errors with stack traces
   - Performance timing

2. **Production Config**
   - Environment variables
   - Database pooling
   - Security settings

3. **Additional Endpoints**
   - Health check (/health)
   - Stats/metrics (/api/stats)
   - Version info (/api/version)

4. **Code Documentation**
   - Docstrings for all functions
   - Inline comments
   - Type hints where helpful

5. **Performance**
   - Request caching
   - Query optimization
   - Connection pooling

## Target

**Final app.py: 300-400 lines minimum** with:
- Complete feature set
- Production-ready code
- Comprehensive error handling
- Full documentation

Make this enterprise-grade!
'''
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated {template_path.name}")


def update_generation_service():
    """Update multi_step_generation_service to use higher max_tokens."""
    service_path = Path(__file__).parent.parent / 'src' / 'app' / 'services' / 'multi_step_generation_service.py'
    
    content = service_path.read_text(encoding='utf-8')
    
    # Update max_tokens default from 8000 to 16000
    content = content.replace(
        'max_tokens: int = 8000',
        'max_tokens: int = 16000'
    )
    
    # Update temperature default to 0.3 for more focused output
    content = content.replace(
        'temperature: float = 0.7',
        'temperature: float = 0.3'
    )
    
    service_path.write_text(content, encoding='utf-8')
    print(f"✓ Updated {service_path.name} (max_tokens=16000, temperature=0.3)")


def main():
    """Run all improvements."""
    print("Applying Comprehensive Improvements")
    print("=" * 60)
    
    update_backend_step1()
    update_backend_step2()
    update_backend_step3()
    update_generation_service()
    
    print("\n" + "=" * 60)
    print("✓ All improvements applied!")
    print("\nNext steps:")
    print("1. Generate fresh apps with new templates")
    print("2. Test all improvements")
    print("3. Verify larger code output (300-400 LOC)")


if __name__ == "__main__":
    main()
