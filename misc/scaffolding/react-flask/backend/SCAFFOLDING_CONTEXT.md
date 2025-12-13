```markdown
# Backend Blueprint Reference

## Stack & Environment
- Flask 3.0, SQLAlchemy, Flask-CORS, Gunicorn/Werkzeug
- Database path: `sqlite:////app/data/app.db` (4 slashes for absolute path)
- Data persistence: `/app/data` directory

## What You Can Generate

### Required Files
- **app.py**: Main Flask application with routes, models, and business logic

### Optional Additional Files (encouraged for complex apps)
- **models.py**: Separate database models if app.py gets large
- **routes.py**: Separate route definitions for complex APIs  
- **utils.py**: Helper functions and utilities
- **services/**: Service layer modules for business logic
- Any other Python modules needed for your implementation

### Dependencies
- Add new requirements by mentioning them or using ```requirements blocks
- Base requirements already included: Flask, SQLAlchemy, Flask-CORS, gunicorn

## Code Structure (Recommended)
```python
# 1. Imports
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os, logging, re

# 2. App setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Upload configuration
UPLOAD_FOLDER = '/app/data/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 3. Models
class YourModel(db.Model):
    __tablename__ = 'your_resources'
    id = db.Column(db.Integer, primary_key=True)
    # Add your fields here
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {'id': self.id, 'created_at': self.created_at.isoformat()}

# 4. Create tables
with app.app_context():
    db.create_all()

# 5. Routes
@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'backend'})

@app.route('/api/YOUR_RESOURCE', methods=['GET'])
def get_resources():
    items = YourModel.query.all()
    return jsonify({'items': [i.to_dict() for i in items], 'total': len(items)})

# 6. Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

# 7. Main
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_RUN_PORT', 5000)))
```

## File Upload Pattern
```python
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return jsonify({'filename': filename, 'url': f'/uploads/{filename}'})

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)
```

## Response Formats
- **List**: `{"items": [...], "total": N}`
- **Single**: `{...item fields...}`
- **Created**: `{...item fields...}` with status 201
- **Error**: `{"error": "message"}` with appropriate status code

## Quality Expectations
- Implement ALL requirements from the specification
- Include proper error handling and validation
- Add logging for important operations
- Use appropriate HTTP status codes
- Generate complete, working code - no placeholders
```
