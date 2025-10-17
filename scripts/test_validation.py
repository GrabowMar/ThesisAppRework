"""Test Code Validation System

Tests the new code validator to ensure it catches common issues.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.code_validator import CodeValidator, validate_generated_code


def test_missing_dependencies():
    """Test detection of missing dependencies."""
    print("=" * 80)
    print("Test 1: Missing Dependencies Detection")
    print("=" * 80)
    
    # Code that uses lxml but doesn't include it in requirements
    app_py = """
from flask import Flask, jsonify
from flask_cors import CORS
from lxml import etree
import logging

app = Flask(__name__)
CORS(app)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""
    
    requirements_txt = """
Flask==3.0.0
Flask-CORS==4.0.0
"""
    
    validator = CodeValidator()
    is_valid, errors, warnings = validator.validate_python_backend(app_py, requirements_txt)
    
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    print(f"Warnings: {warnings}")
    
    if not is_valid and 'lxml' in str(errors):
        print("✓ Test PASSED - correctly detected missing lxml")
    else:
        print("✗ Test FAILED - did not detect missing lxml")
    
    print()


def test_complete_dependencies():
    """Test when all dependencies are present."""
    print("=" * 80)
    print("Test 2: Complete Dependencies")
    print("=" * 80)
    
    app_py = """
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)
db = SQLAlchemy(app)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
"""
    
    requirements_txt = """
Flask==3.0.0
Flask-CORS==4.0.0
Flask-SQLAlchemy==3.1.1
Werkzeug==3.0.1
SQLAlchemy==2.0.25
"""
    
    validator = CodeValidator()
    is_valid, errors, warnings = validator.validate_python_backend(app_py, requirements_txt)
    
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    print(f"Warnings: {warnings}")
    
    if is_valid:
        print("✓ Test PASSED - all dependencies present")
    else:
        print("✗ Test FAILED - reported false errors")
    
    print()


def test_syntax_error():
    """Test detection of syntax errors."""
    print("=" * 80)
    print("Test 3: Syntax Error Detection")
    print("=" * 80)
    
    app_py = """
from flask import Flask

app = Flask(__name__)

@app.route('/health')
def health(
    return jsonify({'status': 'ok'})  # Missing closing paren
"""
    
    requirements_txt = "Flask==3.0.0"
    
    validator = CodeValidator()
    is_valid, errors, warnings = validator.validate_python_backend(app_py, requirements_txt)
    
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    
    if not is_valid and errors:
        print("✓ Test PASSED - syntax error detected")
    else:
        print("✗ Test FAILED - syntax error not detected")
    
    print()


def test_frontend_validation():
    """Test frontend validation."""
    print("=" * 80)
    print("Test 4: Frontend Validation")
    print("=" * 80)
    
    package_json = """
{
  "name": "frontend",
  "type": "module",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
"""
    
    app_jsx = """
import React, { useState } from 'react';
import axios from 'axios';

export default function App() {
  const [data, setData] = useState([]);
  
  const fetchData = async () => {
    try {
      const response = await axios.get('/api/data');
      setData(response.data);
    } catch (error) {
      console.error('Error:', error);
    }
  };
  
  return (
    <div>
      <h1>Test App</h1>
      <button onClick={fetchData}>Fetch Data</button>
    </div>
  );
}
"""
    
    validator = CodeValidator()
    is_valid, errors, warnings = validator.validate_react_frontend(package_json, app_jsx)
    
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    print(f"Warnings: {warnings}")
    
    if is_valid:
        print("✓ Test PASSED - frontend validation passed")
    else:
        print("✗ Test FAILED - reported false errors")
    
    print()


def test_missing_react():
    """Test detection of missing React dependency."""
    print("=" * 80)
    print("Test 5: Missing React Dependency")
    print("=" * 80)
    
    package_json = """
{
  "name": "frontend",
  "dependencies": {
    "axios": "^1.6.0"
  }
}
"""
    
    app_jsx = """
import React from 'react';

export default function App() {
  return <div>Hello</div>;
}
"""
    
    validator = CodeValidator()
    is_valid, errors, warnings = validator.validate_react_frontend(package_json, app_jsx)
    
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    
    if not is_valid and 'react' in str(errors).lower():
        print("✓ Test PASSED - missing react detected")
    else:
        print("✗ Test FAILED - did not detect missing react")
    
    print()


def test_hardcoded_backend_url():
    """Test detection of hardcoded backend URLs."""
    print("=" * 80)
    print("Test 6: Hardcoded Backend URL Detection")
    print("=" * 80)
    
    package_json = """
{
  "name": "frontend",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  }
}
"""
    
    app_jsx = """
import React from 'react';
import axios from 'axios';

export default function App() {
  const fetchData = () => {
    axios.get('http://localhost:5000/api/data');
  };
  
  return <div>App</div>;
}
"""
    
    validator = CodeValidator()
    is_valid, errors, warnings = validator.validate_react_frontend(package_json, app_jsx)
    
    print(f"Valid: {is_valid}")
    print(f"Warnings: {warnings}")
    
    if warnings and 'absolute' in str(warnings).lower():
        print("✓ Test PASSED - hardcoded URL detected")
    else:
        print("✗ Test FAILED - did not detect hardcoded URL")
    
    print()


def test_full_validation():
    """Test full validation with both backend and frontend."""
    print("=" * 80)
    print("Test 7: Full Stack Validation")
    print("=" * 80)
    
    # Good backend
    app_py = """
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""
    
    requirements_txt = """
Flask==3.0.0
Flask-CORS==4.0.0
"""
    
    # Good frontend
    package_json = """
{
  "name": "frontend",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }
}
"""
    
    app_jsx = """
import React from 'react';
export default function App() {
  return <div>Hello</div>;
}
"""
    
    results = validate_generated_code(
        app_py=app_py,
        requirements_txt=requirements_txt,
        package_json=package_json,
        app_jsx=app_jsx
    )
    
    print(f"Overall Valid: {results['overall_valid']}")
    print(f"Backend Valid: {results['backend']['valid']}")
    print(f"Frontend Valid: {results['frontend']['valid']}")
    
    if results['overall_valid']:
        print("✓ Test PASSED - full stack validation passed")
    else:
        print("✗ Test FAILED")
        print(f"Backend errors: {results['backend']['errors']}")
        print(f"Frontend errors: {results['frontend']['errors']}")
    
    print()


def main():
    """Run all validation tests."""
    print("\n" + "=" * 80)
    print("CODE VALIDATION SYSTEM - TEST SUITE")
    print("=" * 80 + "\n")
    
    test_missing_dependencies()
    test_complete_dependencies()
    test_syntax_error()
    test_frontend_validation()
    test_missing_react()
    test_hardcoded_backend_url()
    test_full_validation()
    
    print("=" * 80)
    print("Validation test suite complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
