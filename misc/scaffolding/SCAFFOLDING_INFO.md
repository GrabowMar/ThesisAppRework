# Scaffolding Information

## Project Structure

Your generated code will be merged into an existing scaffolding structure that provides complete Docker infrastructure.

### Backend Scaffolding (Flask)

**Existing Files (DO NOT REGENERATE):**
```
backend/
├── Dockerfile              # Container configuration
├── .dockerignore          # Docker ignore rules
├── requirements.txt       # Python dependencies
└── app.py                 # Base Flask app with health check
```

**Base app.py Structure:**
```python
from flask import Flask, jsonify
from flask_cors import CORS
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'development-secret-key'
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Flask app is running'}), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({'message': 'Flask API is running', 'version': '1.0.0'}), 200

# YOUR APPLICATION CODE WILL BE ADDED HERE

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=5000, debug=True)
```

**Your Task:** Generate additional routes, models, and business logic that will be inserted into this structure.

**Available in requirements.txt:**
- Flask
- flask-cors
- SQLAlchemy
- flask-sqlalchemy

---

### Frontend Scaffolding (React + Vite)

**Existing Files (DO NOT REGENERATE):**
```
frontend/
├── Dockerfile              # Container configuration
├── .dockerignore          # Docker ignore rules
├── nginx.conf             # Nginx web server config
├── vite.config.js         # Vite bundler config with proxy
├── package.json           # NPM dependencies
├── index.html             # HTML entry point
└── src/
    ├── App.css            # Styles for App component
    ├── App.jsx            # Main application component (YOU GENERATE THIS)
    └── main.jsx           # React entry point
```

**Base main.jsx:**
```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './App.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**Your Task:** Generate the complete App.jsx component that implements all frontend requirements.

**Available in package.json:**
- react
- react-dom
- axios (for API calls)
- Vite (build tool)

**API Proxy Configuration:**
The Vite dev server is configured to proxy `/api` requests to the backend, so use:
```jsx
axios.get('/api/todos')  // Will proxy to http://backend:5000/api/todos
```

---

### Docker Infrastructure

**Existing docker-compose.yml:**
```yaml
services:
  backend:
    build: ./backend
    ports: ["5000:5000"]
    volumes: ["./backend:/app"]
    
  frontend:
    build: ./frontend
    ports: ["8000:80"]
    depends_on: [backend]
```

**Important:** Your code runs inside Docker containers with automatic reload on file changes.

---

## Key Constraints

1. **DO NOT generate infrastructure files** (Dockerfile, docker-compose.yml, requirements.txt, package.json, vite.config.js, nginx.conf)
2. **DO generate application code** (routes, models, components, business logic)
3. **Use the scaffolding context** - you're adding to an existing working app
4. **Import properly** - assume all dependencies are already installed
5. **Follow Flask/React best practices** - the scaffolding provides the foundation
