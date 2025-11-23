# Backend Scaffolding Context

## Technical Stack
- **Framework**: Flask (Python 3.11)
- **Database**: SQLAlchemy with SQLite (`app.db`)
- **CORS**: Flask-CORS enabled for all routes
- **Server**: Gunicorn (production) / Werkzeug (dev)

## Architecture Constraints
1. **Entry Point**: `app.py` MUST contain a `setup_app(app)` factory function.
2. **Routing**: ALL API routes MUST start with `/api/` (e.g., `/api/todos`).
   - The frontend is served at root `/`.
   - Nginx proxies `/api/*` to the backend container.
3. **Database**:
   - Use `db = SQLAlchemy()` initialized globally.
   - Models must inherit from `db.Model`.
   - Models must have a `to_dict()` method for JSON serialization.
4. **Configuration**:
   - `SQLALCHEMY_DATABASE_URI` is set to `sqlite:///app.db`.
   - Port is read from `FLASK_RUN_PORT` environment variable (default 5000).
   - Host must be `0.0.0.0` to be accessible from Nginx.

## Code Pattern
```python
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
CORS(app)
db = SQLAlchemy()

def setup_app(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    db.init_app(app)
    with app.app_context():
        db.create_all()

# ... models and routes ...

setup_app(app)

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```
