"""Code Validation Service
========================

Validates generated code for common issues before saving to disk.
Helps prevent runtime errors by catching missing dependencies, syntax errors, etc.
"""

import ast
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CodeValidator:
    """Validates generated code for common issues."""
    
    # Python standard library modules (don't need to be in requirements.txt)
    STDLIB_MODULES = {
        'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
        'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
        'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
        'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
        'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
        'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
        'dis', 'distutils', 'doctest', 'email', 'encodings', 'enum', 'errno', 'faulthandler',
        'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'fractions', 'ftplib', 'functools',
        'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'grp', 'gzip',
        'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr', 'imp',
        'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword',
        'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap',
        'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'multiprocessing',
        'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev',
        'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil',
        'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint', 'profile',
        'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri',
        'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy',
        'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil', 'signal',
        'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3',
        'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess',
        'sunau', 'symbol', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny',
        'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading',
        'time', 'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 'traceback',
        'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing', 'unicodedata',
        'unittest', 'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
        'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc',
        'zipapp', 'zipfile', 'zipimport', 'zlib', '_thread'
    }
    
    def validate_python_backend(
        self, 
        app_py_content: str, 
        requirements_txt_content: str
    ) -> Tuple[bool, List[str], List[str]]:
        """Validate Python backend code.
        
        Args:
            app_py_content: Content of app.py
            requirements_txt_content: Content of requirements.txt
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # 1. Check Python syntax
        try:
            ast.parse(app_py_content)
        except SyntaxError as e:
            errors.append(f"Syntax error in app.py: {e}")
            return False, errors, warnings
        
        # 2. Extract imports from app.py
        imported_packages = self._extract_python_imports(app_py_content)
        
        # 3. Extract packages from requirements.txt
        required_packages = self._extract_requirements(requirements_txt_content)
        
        # 4. Check for missing dependencies
        missing = self._check_missing_dependencies(imported_packages, required_packages)
        
        if missing:
            errors.append(
                f"Missing dependencies in requirements.txt: {', '.join(sorted(missing))}"
            )
        
        # 5. Check for common Flask patterns
        if 'flask' in imported_packages or 'Flask' in app_py_content:
            if 'Flask' not in required_packages and 'flask' not in required_packages:
                errors.append("Flask is imported but not in requirements.txt")
        
        # 6. Check for database setup if SQLAlchemy is used
        if 'flask_sqlalchemy' in imported_packages or 'SQLAlchemy' in app_py_content:
            if 'db.create_all()' not in app_py_content:
                warnings.append("SQLAlchemy is used but db.create_all() not found - database may not initialize")
        
        # 7. Check for CORS if Flask-CORS is imported
        if 'flask_cors' in imported_packages:
            if 'CORS(' not in app_py_content:
                warnings.append("Flask-CORS imported but CORS() not called")
        
        # 8. Check if app runs on port 5000
        if "app.run(" in app_py_content:
            if "port=5000" not in app_py_content and "port = 5000" not in app_py_content:
                warnings.append("Flask app should run on port 5000")
        
        # 9. Check for health endpoint
        if "@app.route('/health'" not in app_py_content and '@app.route("/health"' not in app_py_content:
            warnings.append("No /health endpoint found - health checks may fail")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    def validate_react_frontend(
        self,
        package_json_content: str,
        app_jsx_content: str
    ) -> Tuple[bool, List[str], List[str]]:
        """Validate React frontend code.
        
        Args:
            package_json_content: Content of package.json
            app_jsx_content: Content of App.jsx
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # 1. Check package.json is valid JSON
        import json
        try:
            package_data = json.loads(package_json_content)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in package.json: {e}")
            return False, errors, warnings
        
        # 2. Check for required dependencies
        deps = package_data.get('dependencies', {})
        dev_deps = package_data.get('devDependencies', {})
        all_deps = {**deps, **dev_deps}
        
        if 'react' not in all_deps:
            errors.append("react is not in dependencies")
        if 'react-dom' not in all_deps:
            errors.append("react-dom is not in dependencies")
        if 'axios' not in all_deps:
            warnings.append("axios not in dependencies - API calls may not work")
        if 'vite' not in all_deps and '@vitejs/plugin-react' not in all_deps:
            warnings.append("Vite not configured - build may fail")
        
        # 3. Check App.jsx imports
        if 'import React' not in app_jsx_content and "import { useState" not in app_jsx_content:
            errors.append("App.jsx does not import React or hooks")
        
        if 'import axios' in app_jsx_content and 'axios' not in all_deps:
            errors.append("App.jsx imports axios but it's not in package.json")
        
        # 4. Check for proper React component structure
        if 'export default' not in app_jsx_content and 'export { App }' not in app_jsx_content:
            errors.append("App.jsx does not export a component")
        
        # 5. Check for API calls using absolute URLs (should use relative)
        if 'http://localhost:5000' in app_jsx_content or 'http://localhost:5003' in app_jsx_content:
            warnings.append("App.jsx uses absolute backend URLs - should use relative paths like /api/endpoint")
        
        # 6. Check for error handling on API calls
        if 'axios.' in app_jsx_content or 'fetch(' in app_jsx_content:
            if 'catch' not in app_jsx_content and '.catch(' not in app_jsx_content:
                warnings.append("API calls found but no error handling (try/catch or .catch)")
        
        # 7. Check minimum code size
        if len(app_jsx_content) < 500:
            warnings.append(f"App.jsx is only {len(app_jsx_content)} characters - may be incomplete (expected 2000+)")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    def _extract_python_imports(self, code: str) -> Set[str]:
        """Extract top-level package names from Python import statements."""
        imports = set()
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Get the top-level package name
                        package = alias.name.split('.')[0]
                        imports.add(package)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Get the top-level package name
                        package = node.module.split('.')[0]
                        imports.add(package)
        except SyntaxError:
            # If we can't parse, fall back to regex
            import_re = re.compile(r'^\s*(?:from\s+(\S+)|import\s+(\S+))', re.MULTILINE)
            for match in import_re.finditer(code):
                package = (match.group(1) or match.group(2)).split('.')[0].split()[0]
                imports.add(package)
        
        # Filter out standard library modules
        third_party = {pkg for pkg in imports if pkg not in self.STDLIB_MODULES}
        
        return third_party
    
    def _extract_requirements(self, requirements_txt: str) -> Set[str]:
        """Extract package names from requirements.txt."""
        packages = set()
        
        for line in requirements_txt.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Handle package==version, package>=version, etc.
            package_match = re.match(r'^([a-zA-Z0-9_\-]+)', line)
            if package_match:
                package_name = package_match.group(1).lower().replace('-', '_')
                packages.add(package_name)
        
        return packages
    
    def _check_missing_dependencies(
        self, 
        imported: Set[str], 
        required: Set[str]
    ) -> Set[str]:
        """Check which imported packages are missing from requirements."""
        # Normalize names (e.g., flask_cors vs Flask-CORS)
        normalized_required = set()
        for pkg in required:
            normalized_required.add(pkg.lower().replace('-', '_'))
        
        missing = set()
        for imp in imported:
            normalized_imp = imp.lower().replace('-', '_')
            if normalized_imp not in normalized_required:
                missing.add(imp)
        
        return missing


def validate_generated_code(
    app_py: Optional[str] = None,
    requirements_txt: Optional[str] = None,
    package_json: Optional[str] = None,
    app_jsx: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience function to validate generated code.
    
    Args:
        app_py: Content of app.py (optional)
        requirements_txt: Content of requirements.txt (optional)
        package_json: Content of package.json (optional)
        app_jsx: Content of App.jsx (optional)
        
    Returns:
        Dict with validation results
    """
    validator = CodeValidator()
    results = {
        'backend': {'valid': True, 'errors': [], 'warnings': []},
        'frontend': {'valid': True, 'errors': [], 'warnings': []},
        'overall_valid': True
    }
    
    # Validate backend
    if app_py and requirements_txt:
        is_valid, errors, warnings = validator.validate_python_backend(
            app_py, requirements_txt
        )
        results['backend'] = {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings
        }
        if not is_valid:
            results['overall_valid'] = False
    
    # Validate frontend
    if package_json and app_jsx:
        is_valid, errors, warnings = validator.validate_react_frontend(
            package_json, app_jsx
        )
        results['frontend'] = {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings
        }
        if not is_valid:
            results['overall_valid'] = False
    
    return results
