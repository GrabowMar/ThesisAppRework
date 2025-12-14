"""Tests for the DependencyHealer service."""

import json
import tempfile
from pathlib import Path

import pytest


class TestDependencyHealer:
    """Tests for DependencyHealer class."""

    @pytest.fixture
    def healer(self):
        """Create a DependencyHealer instance."""
        from app.services.dependency_healer import DependencyHealer
        return DependencyHealer(auto_fix=True)

    @pytest.fixture
    def mock_app_dir(self, tmp_path):
        """Create a mock generated app directory structure."""
        # Create frontend structure
        frontend_dir = tmp_path / "frontend"
        src_dir = frontend_dir / "src"
        components_dir = src_dir / "components"
        components_dir.mkdir(parents=True)
        
        # Create package.json with minimal deps
        package_json = {
            "name": "test-app",
            "dependencies": {
                "react": "^18.0.0",
                "react-dom": "^18.0.0"
            }
        }
        (frontend_dir / "package.json").write_text(json.dumps(package_json, indent=2))
        
        # Create backend structure
        backend_dir = tmp_path / "backend"
        backend_dir.mkdir()
        
        # Create requirements.txt with minimal deps
        (backend_dir / "requirements.txt").write_text("Flask==3.0.0\n")
        
        return tmp_path

    def test_healer_initialization(self, healer):
        """Test that healer initializes correctly."""
        assert healer.auto_fix is True
        assert len(healer.KNOWN_NPM_PACKAGES) > 0
        assert len(healer.KNOWN_PYTHON_PACKAGES) > 0

    def test_validate_app_no_issues(self, healer, mock_app_dir):
        """Test validation of app with no issues."""
        result = healer.validate_app(mock_app_dir)
        
        assert result.success is True
        assert result.app_path == str(mock_app_dir)
        assert result.issues_found == 0

    def test_extract_js_imports(self, healer, mock_app_dir):
        """Test JavaScript import extraction."""
        # Create a JS file with various imports
        js_file = mock_app_dir / "frontend" / "src" / "test.js"
        js_file.write_text("""
import React from 'react';
import { useState } from 'react';
import { format } from 'date-fns';
import clsx from 'clsx';
import MyComponent from './MyComponent';
        """)
        
        imports = healer._extract_js_imports(js_file)
        
        assert 'react' in imports
        assert 'date-fns' in imports
        assert 'clsx' in imports
        assert './MyComponent' in imports

    def test_extract_python_imports(self, healer, mock_app_dir):
        """Test Python import extraction."""
        # Create a Python file with various imports
        py_file = mock_app_dir / "backend" / "test.py"
        py_file.write_text("""
import os
import json
from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
from models import User
        """)
        
        imports = healer._extract_python_imports(py_file)
        
        assert 'os' in imports
        assert 'json' in imports
        assert 'flask' in imports
        assert 'flask_cors' in imports
        assert 'requests' in imports
        assert 'datetime' in imports
        assert 'models' in imports

    def test_detect_missing_npm_dependency(self, healer, mock_app_dir):
        """Test detection of missing npm dependencies."""
        # Create a JS file that imports date-fns (not in package.json)
        components_dir = mock_app_dir / "frontend" / "src" / "components"
        js_file = components_dir / "DatePicker.jsx"
        js_file.write_text("""
import React from 'react';
import { format, parseISO } from 'date-fns';

export default function DatePicker({ date }) {
    return <div>{format(parseISO(date), 'PPP')}</div>;
}
        """)
        
        src_dir = mock_app_dir / "frontend" / "src"
        package_json_path = mock_app_dir / "frontend" / "package.json"
        
        missing = healer._find_missing_npm_deps(src_dir, package_json_path)
        
        assert 'date-fns' in missing

    def test_add_npm_dependencies(self, healer, mock_app_dir):
        """Test adding npm dependencies to package.json."""
        from app.services.dependency_healer import HealingResult
        
        package_json_path = mock_app_dir / "frontend" / "package.json"
        result = HealingResult(success=True, app_path=str(mock_app_dir))
        
        healer._add_npm_dependencies(
            package_json_path, 
            {'date-fns', 'clsx'}, 
            result
        )
        
        # Read updated package.json
        updated = json.loads(package_json_path.read_text())
        
        assert 'date-fns' in updated['dependencies']
        assert 'clsx' in updated['dependencies']
        assert result.issues_fixed == 2

    def test_detect_missing_python_dependency(self, healer, mock_app_dir):
        """Test detection of missing Python dependencies."""
        # Create a Python file that imports requests (not in requirements.txt)
        py_file = mock_app_dir / "backend" / "api.py"
        py_file.write_text("""
import requests
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/fetch')
def fetch_data():
    return requests.get('https://api.example.com').json()
        """)
        
        requirements_path = mock_app_dir / "backend" / "requirements.txt"
        
        missing = healer._find_missing_python_deps(mock_app_dir / "backend", requirements_path)
        
        assert 'requests' in missing

    def test_add_python_dependencies(self, healer, mock_app_dir):
        """Test adding Python dependencies to requirements.txt."""
        from app.services.dependency_healer import HealingResult
        
        requirements_path = mock_app_dir / "backend" / "requirements.txt"
        result = HealingResult(success=True, app_path=str(mock_app_dir))
        
        healer._add_python_dependencies(
            requirements_path, 
            {'requests', 'redis'}, 
            result
        )
        
        # Read updated requirements.txt
        updated = requirements_path.read_text()
        
        assert 'requests' in updated
        assert 'redis' in updated
        assert result.issues_fixed == 2

    def test_check_python_syntax_valid(self, healer, mock_app_dir):
        """Test syntax checking with valid Python."""
        py_file = mock_app_dir / "backend" / "valid.py"
        py_file.write_text("""
def hello():
    return "Hello, World!"
        """)
        
        issues = healer._check_python_syntax(mock_app_dir / "backend")
        
        assert len(issues) == 0

    def test_check_python_syntax_invalid(self, healer, mock_app_dir):
        """Test syntax checking with invalid Python."""
        py_file = mock_app_dir / "backend" / "invalid.py"
        py_file.write_text("""
def hello(
    # Missing closing parenthesis
        """)
        
        issues = healer._check_python_syntax(mock_app_dir / "backend")
        
        assert len(issues) > 0
        assert "invalid.py" in issues[0]

    def test_heal_app_full_flow(self, healer, mock_app_dir):
        """Test full healing flow with mixed issues."""
        # Create frontend file with missing dep
        components_dir = mock_app_dir / "frontend" / "src" / "components"
        (components_dir / "TimeAgo.jsx").write_text("""
import React from 'react';
import { formatDistance } from 'date-fns';

export default function TimeAgo({ date }) {
    return <span>{formatDistance(new Date(date), new Date())}</span>;
}
        """)
        
        # Create backend file with missing dep
        (mock_app_dir / "backend" / "external.py").write_text("""
import requests
from flask import jsonify

def fetch_external():
    return requests.get('https://api.example.com').json()
        """)
        
        result = healer.heal_app(mock_app_dir)
        
        assert result.success is True
        assert result.issues_found >= 2  # At least date-fns and requests
        assert result.issues_fixed >= 2

    def test_skip_stdlib_modules(self, healer, mock_app_dir):
        """Test that stdlib modules are not flagged as missing."""
        py_file = mock_app_dir / "backend" / "utils.py"
        py_file.write_text("""
import os
import sys
import json
import datetime
from pathlib import Path
from collections import defaultdict
        """)
        
        requirements_path = mock_app_dir / "backend" / "requirements.txt"
        missing = healer._find_missing_python_deps(mock_app_dir / "backend", requirements_path)
        
        # None of these should be flagged
        assert 'os' not in missing
        assert 'sys' not in missing
        assert 'json' not in missing
        assert 'datetime' not in missing
        assert 'pathlib' not in missing
        assert 'collections' not in missing

    def test_skip_local_imports(self, healer, mock_app_dir):
        """Test that local imports are not flagged as missing."""
        py_file = mock_app_dir / "backend" / "routes.py"
        py_file.write_text("""
from models import User
from services.auth import authenticate
from app import db
from config import settings
        """)
        
        requirements_path = mock_app_dir / "backend" / "requirements.txt"
        missing = healer._find_missing_python_deps(mock_app_dir / "backend", requirements_path)
        
        # Local modules should not be flagged
        assert 'models' not in missing
        assert 'services' not in missing
        assert 'app' not in missing
        assert 'config' not in missing


class TestHealGeneratedApp:
    """Tests for the convenience function."""

    def test_heal_generated_app_function(self, tmp_path):
        """Test the convenience function."""
        from app.services.dependency_healer import heal_generated_app
        
        # Create minimal app structure
        (tmp_path / "frontend" / "src").mkdir(parents=True)
        (tmp_path / "frontend" / "package.json").write_text('{"dependencies": {}}')
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "requirements.txt").write_text("")
        
        result = heal_generated_app(tmp_path, auto_fix=False)
        
        assert result is not None
        assert result.app_path == str(tmp_path)
