# XSD Verifier App - OpenRouter Prompts
**Generated:** October 16, 2025

This document shows the exact prompts that would be sent to OpenRouter API for generating the XSD Verifier application using the new template-based system.

---

## 🔧 Backend Generation Prompt

### System Prompt (Backend)

```
You are an expert Flask developer specializing in production-ready REST APIs.

Your task is to generate ONLY the Flask application code based on the given requirements.

RULES:
- Generate ONLY application code (routes, models, business logic)
- DO NOT generate infrastructure files (Dockerfile, requirements.txt, docker-compose.yml, etc)
- Use Flask best practices and proper project structure
- Use SQLAlchemy for database models when needed
- Include CORS configuration for frontend integration
- Implement ALL specified backend requirements completely
- Add proper error handling, validation, and logging
- Use appropriate HTTP status codes and response formats
- Generate complete, working code - no placeholders or TODOs

Return ONLY the Python code wrapped in ```python code blocks.
```

### User Prompt (Backend)

```markdown
# Prompt Template for Backend Generation

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


---

## Application Specification

**Application Name:** XSD Validator

**Description:** A tool to validate XML documents against XSD schemas

---

## Backend Requirements

- Accept XML file upload via POST endpoint
- Accept XSD schema file upload via POST endpoint
- Validate XML against provided XSD schema using lxml library
- Return validation results with detailed error messages if validation fails
- Store validation history with timestamps in SQLite database
- Provide endpoint to retrieve past validation results

---

## Implementation Guidelines

### Database Models
- Use SQLAlchemy ORM with proper model definitions
- Include timestamps (created_at, updated_at) where appropriate
- Add proper relationships and constraints
- Initialize database with `db.create_all()` in app context

### API Endpoints
- Follow RESTful conventions (GET, POST, PUT, DELETE)
- Use proper HTTP status codes (200, 201, 400, 404, 500)
- Return JSON responses with consistent structure
- Add input validation and error handling

### Error Handling
- Catch and handle exceptions gracefully
- Return meaningful error messages
- Log errors for debugging

### Code Quality
- Add docstrings to functions and classes
- Use type hints where appropriate
- Follow PEP 8 style guidelines
- Keep functions focused and modular

---

## Important Constraints

✅ **DO:**
- Generate complete, working Flask application code
- Include all routes, models, and business logic
- Add proper CORS configuration
- Use SQLAlchemy for database operations
- Include error handling and validation
- Add logging for debugging

❌ **DO NOT:**
- Generate Dockerfile, requirements.txt, or other infrastructure
- Include `if __name__ == '__main__'` block (already in scaffolding)
- Regenerate Flask app initialization (already done)
- Create separate files (generate single code block)

---

## Output Format

Generate ONLY the Python code in a single code block:

```python
# Your complete Flask application code here
# This will be merged with the scaffolding
```

```

---

## 🎨 Frontend Generation Prompt

### System Prompt (Frontend)

```
You are an expert React developer specializing in production-ready web applications.

Your task is to generate ONLY the App.jsx component code based on the given requirements.

RULES:
- Generate ONLY application code (App.jsx component)
- DO NOT generate infrastructure files (package.json, vite.config.js, index.html, Dockerfile, etc)
- Use modern React patterns (functional components, hooks)
- Include all necessary imports (React, axios, useState, useEffect, etc)
- Implement ALL specified frontend requirements completely
- Add proper error handling, loading states, and user feedback
- Use clean, semantic JSX structure
- Include inline styles or use className for CSS (App.css will exist)
- Generate complete, working code - no placeholders or TODOs

Return ONLY the JSX/JavaScript code wrapped in ```jsx code blocks.
```

### User Prompt (Frontend)

```markdown
# Prompt Template for Frontend Generation

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


---

## Application Specification

**Application Name:** XSD Validator

**Description:** A tool to validate XML documents against XSD schemas

---

## Frontend Requirements

- Form to upload XML file (with file input and preview)
- Form to upload XSD schema file (with file input and preview)
- Submit button to trigger validation
- Display validation results clearly (success or error messages)
- Show validation history in a table with timestamps
- Ability to re-run validation on previous submissions
- Loading indicator during validation process
- Error handling for file upload failures

---

## Implementation Guidelines

### Component Structure
- Use functional components with React hooks
- Implement proper state management with useState
- Use useEffect for side effects and data fetching
- Keep components organized and readable

### API Integration
- Use axios for HTTP requests
- Handle loading states during API calls
- Show error messages for failed requests
- Use async/await for cleaner code

### User Experience
- Add loading indicators during operations
- Show success/error feedback to users
- Implement proper form validation
- Use confirmation dialogs for destructive actions

### Styling
- Use className for CSS classes (App.css is available)
- Keep styles clean and responsive
- Use semantic HTML elements
- Ensure mobile-friendly design

### Code Quality
- Add comments for complex logic
- Use descriptive variable and function names
- Handle edge cases and errors
- Keep code DRY (Don't Repeat Yourself)

---

## Important Constraints

✅ **DO:**
- Generate complete, working React App.jsx component
- Include all necessary imports (React, axios, useState, useEffect)
- Implement all specified frontend requirements
- Add proper error handling and loading states
- Use modern React patterns and best practices
- Make API calls to `/api/*` endpoints (proxy configured)

❌ **DO NOT:**
- Generate index.html, package.json, vite.config.js, or infrastructure
- Create separate component files (single App.jsx only)
- Include CSS in the JSX (use className, App.css exists)
- Regenerate main.jsx or React initialization

---

## Output Format

Generate ONLY the JSX/JavaScript code in a single code block:

```jsx
// Your complete React App.jsx component here
// This will replace the scaffolding's App.jsx
```

```

---

## 📊 Prompt Statistics

| Component | System Prompt | User Prompt | Total |
|-----------|--------------|-------------|-------|
| Backend | 788 chars | 5,558 chars | **6,346 chars** |
| Frontend | 824 chars | 5,863 chars | **6,687 chars** |

**Grand Total:** 13,033 characters

---

## 🏗️ Template Structure

Each prompt consists of:

1. **System Prompt** (~450 chars)
   - Role definition (expert Flask/React developer)
   - Task overview (generate ONLY app code)
   - Rules (DO/DON'T lists)
   - Output format (code blocks)

2. **User Prompt** (~8,000-9,000 chars)
   - **Scaffolding Information** (~3,500 chars)
     - Complete Docker infrastructure documentation
     - Existing files that AI should NOT regenerate
     - Base app structure and available dependencies
   - **Application Specification** (~100 chars)
     - App name and description from requirements JSON
   - **Requirements List** (~500 chars)
     - Specific features to implement
   - **Implementation Guidelines** (~2,000 chars)
     - Best practices for Flask/React
     - Code structure and quality standards
   - **Constraints** (~500 chars)
     - DO: Generate complete app code
     - DON'T: Generate infrastructure files
   - **Output Format** (~100 chars)
     - Single code block with all application code

---

## 🎯 Key Improvements

### Old System (Generic)
```python
"You are a Flask developer. Generate an XSD validator with file upload."
```

### New System (Context-Aware)
```python
Scaffolding Info (what exists) + 
Template Structure (how to organize) + 
Requirements (what to build) = 
Complete Prompt (~9,000 chars)
```

The AI now knows:
- ✅ What files already exist (don't regenerate)
- ✅ What structure to follow (Flask app with routes, SQLAlchemy models)
- ✅ What dependencies are available (Flask, SQLAlchemy, React, axios)
- ✅ Exactly what to build (specific requirements list)
- ✅ How to format output (single code block, no infrastructure)

---

## 📝 XSD Verifier Requirements

### Backend Requirements

1. Accept XML file upload via POST endpoint
2. Accept XSD schema file upload via POST endpoint
3. Validate XML against provided XSD schema using lxml library
4. Return validation results with detailed error messages if validation fails
5. Store validation history with timestamps in SQLite database
6. Provide endpoint to retrieve past validation results

### Frontend Requirements

1. Form to upload XML file (with file input and preview)
2. Form to upload XSD schema file (with file input and preview)
3. Submit button to trigger validation
4. Display validation results clearly (success or error messages)
5. Show validation history in a table with timestamps
6. Ability to re-run validation on previous submissions
7. Loading indicator during validation process
8. Error handling for file upload failures

---

## 🚀 Usage

These prompts are sent to OpenRouter API:

```python
# Backend generation
POST https://openrouter.ai/api/v1/chat/completions
{
  "model": "anthropic/claude-3.5-sonnet",
  "messages": [
    {"role": "system", "content": "<backend_system_prompt>"},
    {"role": "user", "content": "<backend_user_prompt>"}
  ],
  "temperature": 0.3,
  "max_tokens": 16000
}

# Frontend generation (similar structure)
```

The AI's response is then merged into the scaffolding to create the complete application.
