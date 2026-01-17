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


class TestJSXExtensionFix:
    """Tests for JSX file extension validation and fixing."""

    @pytest.fixture
    def healer(self):
        """Create a DependencyHealer instance."""
        from app.services.dependency_healer import DependencyHealer
        return DependencyHealer(auto_fix=True)

    def test_detect_jsx_in_js_file(self, healer, tmp_path):
        """Test detection of JSX syntax in .js files."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        # Create a .js file containing JSX
        jsx_file = src_dir / "hooks" / "useAuth.js"
        jsx_file.parent.mkdir(parents=True)
        jsx_file.write_text("""
import { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  
  return (
    <AuthContext.Provider value={{ user, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}
        """)
        
        issues = healer._find_jsx_extension_issues(src_dir)
        
        assert len(issues) == 1
        assert issues[0]['file'] == jsx_file
        assert issues[0]['new_file'].suffix == '.jsx'

    def test_no_false_positive_for_pure_js(self, healer, tmp_path):
        """Test that pure JS files are not flagged."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        # Create a pure .js file without JSX
        pure_js = src_dir / "services" / "api.js"
        pure_js.parent.mkdir(parents=True)
        pure_js.write_text("""
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

export const getUsers = () => api.get('/users');
export const createUser = (data) => api.post('/users', data);
        """)
        
        issues = healer._find_jsx_extension_issues(src_dir)
        
        assert len(issues) == 0

    def test_fix_jsx_extension(self, healer, tmp_path):
        """Test automatic renaming of .js files with JSX to .jsx."""
        from app.services.dependency_healer import HealingResult
        
        src_dir = tmp_path / "frontend" / "src"
        hooks_dir = src_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        
        # Create a .js file containing JSX
        jsx_file = hooks_dir / "useAuth.js"
        jsx_file.write_text("""
export function AuthProvider({ children }) {
  return <div>{children}</div>;
}
        """)
        
        result = HealingResult(success=True, app_path=str(tmp_path))
        issues = healer._find_jsx_extension_issues(src_dir)
        healer._fix_jsx_extensions(issues, result)
        
        # Original file should be gone
        assert not jsx_file.exists()
        # New .jsx file should exist
        assert (hooks_dir / "useAuth.jsx").exists()
        assert result.issues_fixed == 1
        assert any("Renamed" in change for change in result.changes_made)

    def test_full_heal_includes_jsx_fix(self, healer, tmp_path):
        """Test that heal_app includes JSX extension fix."""
        # Create app structure
        frontend_dir = tmp_path / "frontend"
        src_dir = frontend_dir / "src" / "hooks"
        src_dir.mkdir(parents=True)
        
        (frontend_dir / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')
        
        # Create problematic file
        jsx_file = src_dir / "useAuth.js"
        jsx_file.write_text("""
import { createContext } from 'react';
export function Provider({ children }) {
  return <AuthContext.Provider>{children}</AuthContext.Provider>;
}
        """)
        
        # Create backend structure (required)
        backend_dir = tmp_path / "backend"
        backend_dir.mkdir()
        (backend_dir / "requirements.txt").write_text("Flask==3.0.0\n")
        
        result = healer.heal_app(tmp_path)
        
        # Should have fixed the JSX extension
        assert not jsx_file.exists()
        assert (src_dir / "useAuth.jsx").exists()
        assert result.issues_fixed >= 1

    def test_jsx_patterns_comprehensive(self, healer, tmp_path):
        """Test that various JSX patterns are detected."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        test_cases = [
            ("component.js", "<MyComponent />", True),
            ("fragment.js", "return <><div>Test</div></>", True),
            ("html.js", "return <div className='test'>Hello</div>", True),
            ("closing.js", "return <Component>text</Component>", True),
            ("plain.js", "const x = 1; // <Component>", False),  # Comment only
            ("template.js", "const html = `<div>not jsx</div>`", False),  # Template literal
        ]
        
        for filename, content, should_detect in test_cases:
            file_path = src_dir / filename
            file_path.write_text(f"function Test() {{ {content} }}")
        
        issues = healer._find_jsx_extension_issues(src_dir)
        detected_files = {i['file'].name for i in issues}
        
        for filename, _, should_detect in test_cases:
            if should_detect:
                assert filename in detected_files, f"Should detect JSX in {filename}"
            else:
                assert filename not in detected_files, f"False positive for {filename}"


class TestHeroiconsImportFix:
    """Tests for heroicons v1->v2 import path fixes."""

    @pytest.fixture
    def healer(self):
        """Create a DependencyHealer instance."""
        from app.services.dependency_healer import DependencyHealer
        return DependencyHealer(auto_fix=True)

    def test_fix_heroicons_v1_solid_import(self, healer, tmp_path):
        """Test fixing @heroicons/react/solid -> @heroicons/react/24/solid."""
        src_dir = tmp_path / "frontend" / "src" / "pages"
        src_dir.mkdir(parents=True)
        
        # Create file with old v1 import
        jsx_file = src_dir / "AdminPage.jsx"
        jsx_file.write_text("""
import React from 'react';
import { CheckIcon, XIcon } from '@heroicons/react/solid';

export default function AdminPage() {
    return <CheckIcon />;
}
        """)
        
        result = healer._fix_heroicons_imports(src_dir.parent, auto_fix=True)
        
        assert result['fixed_count'] >= 1
        assert any('heroicons' in issue for issue in result['issues'])
        
        # Verify the file was updated
        updated_content = jsx_file.read_text()
        assert "@heroicons/react/24/solid" in updated_content
        assert "@heroicons/react/solid'" not in updated_content

    def test_fix_heroicons_v1_outline_import(self, healer, tmp_path):
        """Test fixing @heroicons/react/outline -> @heroicons/react/24/outline."""
        src_dir = tmp_path / "frontend" / "src" / "components"
        src_dir.mkdir(parents=True)
        
        jsx_file = src_dir / "Button.jsx"
        jsx_file.write_text("""
import { PlusIcon } from '@heroicons/react/outline';
export const Button = () => <PlusIcon />;
        """)
        
        result = healer._fix_heroicons_imports(src_dir.parent, auto_fix=True)
        
        assert result['fixed_count'] >= 1
        
        updated_content = jsx_file.read_text()
        assert "@heroicons/react/24/outline" in updated_content

    def test_fix_heroicons_icon_renames(self, healer, tmp_path):
        """Test fixing renamed icons from v1 to v2 (e.g., XIcon -> XMarkIcon)."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        jsx_file = src_dir / "Modal.jsx"
        jsx_file.write_text("""
import { XIcon, MenuIcon, SearchIcon } from '@heroicons/react/solid';
export const Modal = () => (
    <>
        <XIcon onClick={close} />
        <MenuIcon />
        <SearchIcon />
    </>
);
        """)
        
        result = healer._fix_heroicons_imports(src_dir, auto_fix=True)
        
        updated_content = jsx_file.read_text()
        # XIcon should become XMarkIcon
        assert 'XMarkIcon' in updated_content
        assert 'XIcon' not in updated_content
        # MenuIcon should become Bars3Icon
        assert 'Bars3Icon' in updated_content
        assert 'MenuIcon' not in updated_content
        # SearchIcon should become MagnifyingGlassIcon
        assert 'MagnifyingGlassIcon' in updated_content
        assert 'SearchIcon' not in updated_content

    def test_no_change_for_correct_heroicons_v2(self, healer, tmp_path):
        """Test that correct v2 imports are not modified."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        original_content = """
import { CheckIcon, XMarkIcon } from '@heroicons/react/24/solid';
export const Icon = () => <CheckIcon />;
        """
        jsx_file = src_dir / "Icon.jsx"
        jsx_file.write_text(original_content)
        
        result = healer._fix_heroicons_imports(src_dir, auto_fix=True)
        
        # No changes should be made
        assert result['fixed_count'] == 0
        assert jsx_file.read_text() == original_content


class TestRelativeImportPathFix:
    """Tests for relative import path corrections."""

    @pytest.fixture
    def healer(self):
        """Create a DependencyHealer instance."""
        from app.services.dependency_healer import DependencyHealer
        return DependencyHealer(auto_fix=True)

    def test_fix_services_import_from_pages(self, healer, tmp_path):
        """Test fixing ./services/api -> ../services/api from pages directory."""
        src_dir = tmp_path / "frontend" / "src"
        pages_dir = src_dir / "pages"
        services_dir = src_dir / "services"
        pages_dir.mkdir(parents=True)
        services_dir.mkdir(parents=True)
        
        # Create the target file (api.js)
        (services_dir / "api.js").write_text("export const api = {}; export default api;")
        
        # Create page with wrong import path
        admin_page = pages_dir / "AdminPage.jsx"
        admin_page.write_text("""
import React from 'react';
import { getAdminStats } from './services/api';

export default function AdminPage() {
    return <div>Admin</div>;
}
        """)
        
        result = healer._fix_relative_import_paths(src_dir, auto_fix=True)
        
        assert result['fixed_count'] >= 1
        
        updated_content = admin_page.read_text()
        assert "../services/api" in updated_content
        # Check that the OLD wrong pattern is no longer present (distinguish from ../services/api)
        assert "from './services/api'" not in updated_content

    def test_fix_hooks_import_from_pages(self, healer, tmp_path):
        """Test fixing ./hooks/useAuth -> ../hooks/useAuth from pages directory."""
        src_dir = tmp_path / "frontend" / "src"
        pages_dir = src_dir / "pages"
        hooks_dir = src_dir / "hooks"
        pages_dir.mkdir(parents=True)
        hooks_dir.mkdir(parents=True)
        
        # Create target hook file
        (hooks_dir / "useAuth.jsx").write_text("export const useAuth = () => {};")
        
        # Create page with wrong import
        user_page = pages_dir / "UserPage.jsx"
        user_page.write_text("""
import { useAuth } from './hooks/useAuth';
export default function UserPage() { return <div />; }
        """)
        
        result = healer._fix_relative_import_paths(src_dir, auto_fix=True)
        
        assert result['fixed_count'] >= 1
        
        updated_content = user_page.read_text()
        assert "../hooks/useAuth" in updated_content

    def test_no_change_for_correct_paths(self, healer, tmp_path):
        """Test that already correct paths are not modified."""
        src_dir = tmp_path / "frontend" / "src"
        pages_dir = src_dir / "pages"
        services_dir = src_dir / "services"
        pages_dir.mkdir(parents=True)
        services_dir.mkdir(parents=True)
        
        (services_dir / "api.js").write_text("export const api = {};")
        
        original_content = """
import { getItems } from '../services/api';
export default function Page() { return <div />; }
        """
        page_file = pages_dir / "Page.jsx"
        page_file.write_text(original_content)
        
        result = healer._fix_relative_import_paths(src_dir, auto_fix=True)
        
        # No changes should be made
        assert result['fixed_count'] == 0

    def test_no_change_for_local_sibling_imports(self, healer, tmp_path):
        """Test that local sibling imports (./SiblingComponent) are not changed."""
        src_dir = tmp_path / "frontend" / "src"
        pages_dir = src_dir / "pages"
        pages_dir.mkdir(parents=True)
        
        # Create sibling component
        (pages_dir / "Sidebar.jsx").write_text("export default function Sidebar() {}")
        
        original_content = """
import Sidebar from './Sidebar';
export default function Page() { return <Sidebar />; }
        """
        page_file = pages_dir / "Page.jsx"
        page_file.write_text(original_content)
        
        result = healer._fix_relative_import_paths(src_dir, auto_fix=True)
        
        # Should not change valid local imports
        assert "./Sidebar" in page_file.read_text()


class TestReactHotToastFix:
    """Tests for react-hot-toast import fixes (ToastContainer -> Toaster)."""

    @pytest.fixture
    def healer(self):
        """Create a DependencyHealer instance."""
        from app.services.dependency_healer import DependencyHealer
        return DependencyHealer(auto_fix=True)

    def test_fix_toast_container_import(self, healer, tmp_path):
        """Test fixing ToastContainer import to Toaster for react-hot-toast."""
        src_dir = tmp_path / "frontend" / "src" / "pages"
        src_dir.mkdir(parents=True)
        
        jsx_file = src_dir / "AdminPage.jsx"
        jsx_file.write_text("""
import React from 'react';
import { ToastContainer, toast } from 'react-hot-toast';

export default function AdminPage() {
    return (
        <div>
            <ToastContainer />
            <button onClick={() => toast.success('Done!')}>Click</button>
        </div>
    );
}
        """)
        
        result = healer._fix_react_hot_toast_usage(src_dir.parent, auto_fix=True)
        
        assert result['fixed_count'] >= 1
        assert any('ToastContainer' in issue for issue in result['issues'])
        
        updated_content = jsx_file.read_text()
        assert "import { Toaster" in updated_content
        assert "ToastContainer" not in updated_content
        assert "<Toaster" in updated_content

    def test_no_change_for_correct_toaster(self, healer, tmp_path):
        """Test that correct Toaster usage is not modified."""
        src_dir = tmp_path / "frontend" / "src" / "pages"
        src_dir.mkdir(parents=True)
        
        original_content = """
import { Toaster, toast } from 'react-hot-toast';
export function App() { return <Toaster />; }
        """
        jsx_file = src_dir / "App.jsx"
        jsx_file.write_text(original_content)
        
        result = healer._fix_react_hot_toast_usage(src_dir.parent, auto_fix=True)
        
        assert result['fixed_count'] == 0
        assert jsx_file.read_text() == original_content

    def test_no_change_for_react_toastify(self, healer, tmp_path):
        """Test that react-toastify's ToastContainer is not modified."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        original_content = """
import { ToastContainer, toast } from 'react-toastify';
export function App() { return <ToastContainer />; }
        """
        jsx_file = src_dir / "App.jsx"
        jsx_file.write_text(original_content)
        
        result = healer._fix_react_hot_toast_usage(src_dir, auto_fix=True)
        
        # Should not change react-toastify usage
        assert result['fixed_count'] == 0
        assert "ToastContainer" in jsx_file.read_text()

    def test_fix_only_import_keeps_toast_function(self, healer, tmp_path):
        """Test that toast function calls are preserved when fixing imports."""
        src_dir = tmp_path / "frontend" / "src"
        src_dir.mkdir(parents=True)
        
        jsx_file = src_dir / "App.jsx"
        jsx_file.write_text("""
import { ToastContainer, toast } from 'react-hot-toast';
export function App() {
    const notify = () => toast.success('Hello!');
    return <><ToastContainer /><button onClick={notify}>Notify</button></>;
}
        """)
        
        result = healer._fix_react_hot_toast_usage(src_dir, auto_fix=True)
        
        assert result['fixed_count'] >= 1
        
        updated_content = jsx_file.read_text()
        assert "Toaster" in updated_content
        assert "toast.success" in updated_content  # toast function preserved