"""Dependency Healer Service
============================

Post-generation validation and auto-healing of dependency issues.

This module scans generated apps for common issues that cause build failures:
1. Missing npm/pip dependencies referenced in code but not in package.json/requirements.txt
2. Export mismatches (named vs default exports in JavaScript/JSX)
3. Import errors (importing non-existent modules)

The healer can automatically fix these issues or report them for manual review.
"""

import ast
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HealingResult:
    """Result of dependency healing operation."""
    success: bool
    app_path: str
    issues_found: int = 0
    issues_fixed: int = 0
    frontend_issues: List[str] = field(default_factory=list)
    backend_issues: List[str] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class DependencyHealer:
    """
    Scans and heals dependency issues in generated apps.
    
    Usage:
        healer = DependencyHealer()
        result = healer.heal_app(app_dir)
        
        # Or just validate without fixing:
        result = healer.validate_app(app_dir)
    """
    
    # Common npm packages that AI models frequently use
    KNOWN_NPM_PACKAGES: Dict[str, str] = {
        # Date/time utilities
        'date-fns': '^3.0.0',
        'dayjs': '^1.11.10',
        'moment': '^2.30.1',
        'luxon': '^3.4.4',
        
        # UI libraries
        'clsx': '^2.1.0',
        'classnames': '^2.5.1',
        'tailwind-merge': '^2.2.0',
        'framer-motion': '^11.0.0',
        
        # State management
        'zustand': '^4.5.0',
        'jotai': '^2.6.0',
        'recoil': '^0.7.7',
        
        # Utilities
        'uuid': '^9.0.0',
        'lodash': '^4.17.21',
        'lodash-es': '^4.17.21',
        'immer': '^10.0.3',
        
        # Forms
        'react-hook-form': '^7.49.0',
        'formik': '^2.4.5',
        'yup': '^1.3.3',
        'zod': '^3.22.4',
        
        # Data fetching
        'swr': '^2.2.4',
        '@tanstack/react-query': '^5.17.0',
        
        # Charts/visualization
        'recharts': '^2.10.3',
        'chart.js': '^4.4.1',
        'react-chartjs-2': '^5.2.0',
        
        # Other common
        'dompurify': '^3.0.8',
        'marked': '^11.1.1',
        'nanoid': '^5.0.4',
    }
    
    # Common Python packages that AI models frequently use
    KNOWN_PYTHON_PACKAGES: Dict[str, str] = {
        # Web
        'flask': 'Flask==3.0.0',
        'flask_cors': 'Flask-CORS==4.0.0',
        'flask_sqlalchemy': 'Flask-SQLAlchemy==3.1.1',
        'flask_jwt_extended': 'Flask-JWT-Extended==4.6.0',
        'flask_login': 'Flask-Login==0.6.3',
        'flask_mail': 'Flask-Mail==0.9.1',
        'flask_migrate': 'Flask-Migrate==4.0.5',
        'flask_wtf': 'Flask-WTF==1.2.1',
        
        # Database
        'sqlalchemy': 'SQLAlchemy==2.0.25',
        'psycopg2': 'psycopg2-binary==2.9.9',
        'psycopg2_binary': 'psycopg2-binary==2.9.9',
        'pymysql': 'PyMySQL==1.1.0',
        'redis': 'redis==5.0.1',
        
        # Auth/Security
        'bcrypt': 'bcrypt==4.1.2',
        'pyjwt': 'PyJWT==2.8.0',
        'passlib': 'passlib==1.7.4',
        'werkzeug': 'Werkzeug==3.0.1',
        
        # HTTP/API
        'requests': 'requests==2.31.0',
        'httpx': 'httpx==0.26.0',
        'aiohttp': 'aiohttp==3.9.1',
        
        # Data processing
        'pandas': 'pandas==2.1.4',
        'numpy': 'numpy==1.26.3',
        'pydantic': 'pydantic==2.5.3',
        
        # Utils
        'python_dotenv': 'python-dotenv==1.0.1',
        'celery': 'celery==5.3.6',
        'marshmallow': 'marshmallow==3.20.1',
        'arrow': 'arrow==1.3.0',
        'dateutil': 'python-dateutil==2.8.2',
        
        # Email
        'sendgrid': 'sendgrid==6.11.0',
        
        # File handling
        'pillow': 'Pillow==10.2.0',
        'python_magic': 'python-magic==0.4.27',
    }
    
    # Python standard library modules (should not be in requirements.txt)
    PYTHON_STDLIB: Set[str] = {
        'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
        'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
        'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
        'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
        'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg',
        'cProfile', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime',
        'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email',
        'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
        'fnmatch', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
        'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac',
        'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect',
        'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
        'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes',
        'mmap', 'modulefinder', 'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers',
        'operator', 'optparse', 'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle',
        'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib', 'poplib', 'posix',
        'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile',
        'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib',
        'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 'selectors',
        'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr',
        'socket', 'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat', 'statistics',
        'string', 'stringprep', 'struct', 'subprocess', 'sunau', 'symtable', 'sys',
        'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios',
        'test', 'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'token',
        'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo',
        'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 'venv',
        'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound', 'wsgiref',
        'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo',
        # Common aliases
        'timezone', 'path', 'tz',
    }
    
    # Local/project modules (should not be in requirements.txt)
    LOCAL_PREFIXES: Set[str] = {
        'app', 'models', 'routes', 'services', 'utils', 'config', 'db',
        'api', 'schemas', 'middleware', 'helpers', 'tests', 'migrations',
    }

    def __init__(self, auto_fix: bool = True):
        """
        Initialize the dependency healer.
        
        Args:
            auto_fix: If True, automatically fix issues. If False, only report them.
        """
        self.auto_fix = auto_fix

    def heal_app(self, app_dir: Path) -> HealingResult:
        """
        Scan and heal dependency issues in a generated app.
        
        Args:
            app_dir: Path to the generated app directory
            
        Returns:
            HealingResult with details of issues found and fixed
        """
        app_dir = Path(app_dir)
        result = HealingResult(success=True, app_path=str(app_dir))
        
        logger.info(f"[DependencyHealer] Healing app at: {app_dir}")
        
        try:
            # Heal frontend
            frontend_dir = app_dir / 'frontend'
            if frontend_dir.exists():
                self._heal_frontend(frontend_dir, result)
            
            # Heal backend
            backend_dir = app_dir / 'backend'
            if backend_dir.exists():
                self._heal_backend(backend_dir, result)
            
            # Determine overall success
            result.success = len(result.errors) == 0
            
            # Log summary
            if result.issues_found > 0:
                logger.info(
                    f"[DependencyHealer] Found {result.issues_found} issues, "
                    f"fixed {result.issues_fixed}"
                )
            else:
                logger.info("[DependencyHealer] No issues found")
                
        except Exception as e:
            logger.error(f"[DependencyHealer] Error healing app: {e}")
            result.errors.append(str(e))
            result.success = False
        
        return result

    def validate_app(self, app_dir: Path) -> HealingResult:
        """
        Validate app dependencies without fixing them.
        
        Args:
            app_dir: Path to the generated app directory
            
        Returns:
            HealingResult with details of issues found
        """
        # Temporarily disable auto-fix
        original_auto_fix = self.auto_fix
        self.auto_fix = False
        try:
            return self.heal_app(app_dir)
        finally:
            self.auto_fix = original_auto_fix

    # =========================================================================
    # Frontend Healing
    # =========================================================================
    
    def _heal_frontend(self, frontend_dir: Path, result: HealingResult) -> None:
        """Heal frontend-specific issues."""
        src_dir = frontend_dir / 'src'
        package_json_path = frontend_dir / 'package.json'
        
        if not src_dir.exists():
            logger.warning(f"[DependencyHealer] Frontend src/ not found: {src_dir}")
            return
        
        # 1. Scan for missing npm dependencies
        missing_deps = self._find_missing_npm_deps(src_dir, package_json_path)
        if missing_deps:
            for dep in missing_deps:
                result.frontend_issues.append(f"Missing npm dependency: {dep}")
                result.issues_found += 1
            
            if self.auto_fix:
                self._add_npm_dependencies(package_json_path, missing_deps, result)
        
        # 2. Check export patterns in components
        export_issues = self._check_frontend_exports(src_dir)
        if export_issues:
            for issue in export_issues:
                result.frontend_issues.append(issue['message'])
                result.issues_found += 1
            
            if self.auto_fix:
                self._fix_frontend_exports(export_issues, result)

    def _find_missing_npm_deps(self, src_dir: Path, package_json_path: Path) -> Set[str]:
        """Find npm packages imported in code but not in package.json."""
        # Get installed dependencies
        installed_deps: Set[str] = set()
        if package_json_path.exists():
            try:
                pkg = json.loads(package_json_path.read_text(encoding='utf-8'))
                installed_deps.update(pkg.get('dependencies', {}).keys())
                installed_deps.update(pkg.get('devDependencies', {}).keys())
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"[DependencyHealer] Failed to parse package.json: {e}")
        
        # Scan all JS/JSX/TS/TSX files for imports
        imported_packages: Set[str] = set()
        for ext in ['*.js', '*.jsx', '*.ts', '*.tsx']:
            for file in src_dir.rglob(ext):
                imports = self._extract_js_imports(file)
                imported_packages.update(imports)
        
        # Filter to find missing external packages
        missing: Set[str] = set()
        for pkg in imported_packages:
            # Skip local imports (relative paths)
            if pkg.startswith('.') or pkg.startswith('/'):
                continue
            
            # Skip React (always available)
            if pkg in {'react', 'react-dom', 'react-router-dom'}:
                continue
            
            # Get base package name (handle scoped packages like @heroicons/react)
            base_pkg = pkg.split('/')[0] if not pkg.startswith('@') else '/'.join(pkg.split('/')[:2])
            
            # Check if installed
            if base_pkg not in installed_deps:
                # Only flag if we know about this package
                if base_pkg in self.KNOWN_NPM_PACKAGES or pkg in self.KNOWN_NPM_PACKAGES:
                    missing.add(base_pkg)
                    logger.debug(f"[DependencyHealer] Missing npm dep: {base_pkg}")
        
        return missing

    def _extract_js_imports(self, file_path: Path) -> Set[str]:
        """Extract import statements from a JavaScript/TypeScript file."""
        imports: Set[str] = set()
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Match ES6 imports: import X from 'package'
            es6_pattern = re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]")
            imports.update(es6_pattern.findall(content))
            
            # Match dynamic imports: import('package')
            dynamic_pattern = re.compile(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
            imports.update(dynamic_pattern.findall(content))
            
            # Match require: require('package')
            require_pattern = re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
            imports.update(require_pattern.findall(content))
            
        except Exception as e:
            logger.debug(f"[DependencyHealer] Failed to parse {file_path}: {e}")
        
        return imports

    def _add_npm_dependencies(self, package_json_path: Path, deps: Set[str], result: HealingResult) -> None:
        """Add missing npm dependencies to package.json."""
        if not package_json_path.exists():
            result.errors.append(f"Cannot add deps: package.json not found at {package_json_path}")
            return
        
        try:
            pkg = json.loads(package_json_path.read_text(encoding='utf-8'))
            dependencies = pkg.setdefault('dependencies', {})
            
            added = []
            for dep in deps:
                if dep not in dependencies:
                    version = self.KNOWN_NPM_PACKAGES.get(dep, '*')
                    dependencies[dep] = version
                    added.append(f"{dep}@{version}")
            
            if added:
                # Write updated package.json
                package_json_path.write_text(
                    json.dumps(pkg, indent=2) + '\n',
                    encoding='utf-8'
                )
                result.changes_made.append(f"Added npm dependencies: {', '.join(added)}")
                result.issues_fixed += len(added)
                logger.info(f"[DependencyHealer] Added npm deps: {', '.join(added)}")
                
        except Exception as e:
            result.errors.append(f"Failed to update package.json: {e}")
            logger.error(f"[DependencyHealer] Failed to update package.json: {e}")

    def _check_frontend_exports(self, src_dir: Path) -> List[Dict]:
        """Check for export pattern mismatches in frontend components."""
        issues = []
        
        # Check components/index.js for export pattern consistency
        components_dir = src_dir / 'components'
        if components_dir.exists():
            index_file = components_dir / 'index.js'
            if index_file.exists():
                issues.extend(self._check_index_exports(index_file, components_dir))
        
        # Check pages/index.js
        pages_dir = src_dir / 'pages'
        if pages_dir.exists():
            index_file = pages_dir / 'index.js'
            if index_file.exists():
                issues.extend(self._check_index_exports(index_file, pages_dir))
        
        return issues

    def _check_index_exports(self, index_file: Path, component_dir: Path) -> List[Dict]:
        """Check that index.js exports match actual component exports."""
        issues = []
        
        try:
            index_content = index_file.read_text(encoding='utf-8')
            
            # Pattern: export { default as Name } from './Name' (expects default export)
            default_export_pattern = re.compile(
                r"export\s*\{\s*default\s+as\s+(\w+)\s*\}\s*from\s*['\"]\.\/(\w+)['\"]"
            )
            
            # Pattern: export { Name } from './Name' (expects named export)
            named_export_pattern = re.compile(
                r"export\s*\{\s*(\w+)\s*\}\s*from\s*['\"]\.\/(\w+)['\"]"
            )
            
            # Check default export pattern usage
            for match in default_export_pattern.finditer(index_content):
                export_name = match.group(1)
                file_name = match.group(2)
                
                # Find the component file
                component_file = None
                for ext in ['.jsx', '.js', '.tsx', '.ts']:
                    candidate = component_dir / f"{file_name}{ext}"
                    if candidate.exists():
                        component_file = candidate
                        break
                
                if component_file:
                    # Check if component has default export
                    comp_content = component_file.read_text(encoding='utf-8')
                    has_default = bool(re.search(r'export\s+default\s+', comp_content))
                    
                    if not has_default:
                        issues.append({
                            'type': 'export_mismatch',
                            'index_file': str(index_file),
                            'component_file': str(component_file),
                            'export_name': export_name,
                            'message': f"index.js expects default export from {file_name}, but component uses named export",
                            'fix': 'convert_to_default'
                        })
            
            # Check named export pattern usage
            for match in named_export_pattern.finditer(index_content):
                export_name = match.group(1)
                file_name = match.group(2)
                
                # Skip if it's actually a 'default as' pattern (already handled)
                if f"default as {export_name}" in index_content:
                    continue
                
                # Find the component file
                component_file = None
                for ext in ['.jsx', '.js', '.tsx', '.ts']:
                    candidate = component_dir / f"{file_name}{ext}"
                    if candidate.exists():
                        component_file = candidate
                        break
                
                if component_file:
                    # Check if component has the named export
                    comp_content = component_file.read_text(encoding='utf-8')
                    has_named = bool(re.search(
                        rf'export\s+(?:function|const|class|let|var)\s+{re.escape(export_name)}',
                        comp_content
                    ))
                    has_default = bool(re.search(r'export\s+default\s+', comp_content))
                    
                    if not has_named and has_default:
                        issues.append({
                            'type': 'export_mismatch',
                            'index_file': str(index_file),
                            'component_file': str(component_file),
                            'export_name': export_name,
                            'message': f"index.js expects named export '{export_name}' from {file_name}, but component uses default export",
                            'fix': 'update_index_to_default'
                        })
                        
        except Exception as e:
            logger.warning(f"[DependencyHealer] Failed to check exports in {index_file}: {e}")
        
        return issues

    def _fix_frontend_exports(self, issues: List[Dict], result: HealingResult) -> None:
        """Fix export pattern mismatches."""
        for issue in issues:
            try:
                if issue['fix'] == 'convert_to_default':
                    # Convert component from named export to default export
                    self._convert_to_default_export(Path(issue['component_file']), issue['export_name'])
                    result.changes_made.append(f"Converted {issue['export_name']} to default export")
                    result.issues_fixed += 1
                    
                elif issue['fix'] == 'update_index_to_default':
                    # Update index.js to use 'default as' pattern
                    self._update_index_to_default(
                        Path(issue['index_file']),
                        issue['export_name']
                    )
                    result.changes_made.append(f"Updated index.js to use default export for {issue['export_name']}")
                    result.issues_fixed += 1
                    
            except Exception as e:
                result.errors.append(f"Failed to fix export issue: {e}")
                logger.error(f"[DependencyHealer] Failed to fix export: {e}")

    def _convert_to_default_export(self, file_path: Path, export_name: str) -> None:
        """Convert a named export to a default export."""
        content = file_path.read_text(encoding='utf-8')
        
        # Pattern: export function Name(...) or export const Name = ...
        # Convert to: function Name(...) + export default Name;
        
        # Handle export function Name
        content = re.sub(
            rf'^export\s+(function\s+{re.escape(export_name)}\s*\([^)]*\)\s*\{{)',
            r'\1',
            content,
            flags=re.MULTILINE
        )
        
        # Handle export class Name
        content = re.sub(
            rf'^export\s+(class\s+{re.escape(export_name)}\s+)',
            r'\1',
            content,
            flags=re.MULTILINE
        )
        
        # Handle export const Name
        content = re.sub(
            rf'^export\s+(const\s+{re.escape(export_name)}\s*=)',
            r'\1',
            content,
            flags=re.MULTILINE
        )
        
        # Add default export at end if not present
        if 'export default' not in content:
            content = content.rstrip() + f'\n\nexport default {export_name};\n'
        
        file_path.write_text(content, encoding='utf-8')
        logger.info(f"[DependencyHealer] Converted {export_name} to default export in {file_path.name}")

    def _update_index_to_default(self, index_file: Path, export_name: str) -> None:
        """Update index.js to use 'export { default as X }' pattern."""
        content = index_file.read_text(encoding='utf-8')
        
        # Find the file name from existing export
        match = re.search(
            rf"export\s*\{{\s*{re.escape(export_name)}\s*\}}\s*from\s*['\"]\.\/(\w+)['\"]",
            content
        )
        
        if match:
            file_name = match.group(1)
            old_pattern = match.group(0)
            new_pattern = f"export {{ default as {export_name} }} from './{file_name}'"
            content = content.replace(old_pattern, new_pattern)
            index_file.write_text(content, encoding='utf-8')
            logger.info(f"[DependencyHealer] Updated index.js export pattern for {export_name}")

    # =========================================================================
    # Backend Healing
    # =========================================================================
    
    def _heal_backend(self, backend_dir: Path, result: HealingResult) -> None:
        """Heal backend-specific issues."""
        requirements_path = backend_dir / 'requirements.txt'
        
        # 1. Scan Python files for missing dependencies
        missing_deps = self._find_missing_python_deps(backend_dir, requirements_path)
        if missing_deps:
            for dep in missing_deps:
                result.backend_issues.append(f"Missing Python dependency: {dep}")
                result.issues_found += 1
            
            if self.auto_fix:
                self._add_python_dependencies(requirements_path, missing_deps, result)
        
        # 2. Check for Python syntax errors
        syntax_issues = self._check_python_syntax(backend_dir)
        if syntax_issues:
            for issue in syntax_issues:
                result.backend_issues.append(issue)
                result.issues_found += 1
            # Syntax errors can't be auto-fixed

    def _find_missing_python_deps(self, backend_dir: Path, requirements_path: Path) -> Set[str]:
        """Find Python packages imported in code but not in requirements.txt."""
        # Get installed dependencies
        installed_deps: Set[str] = set()
        if requirements_path.exists():
            try:
                content = requirements_path.read_text(encoding='utf-8')
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name (before version specifier)
                        pkg_name = re.split(r'[<>=!~\[]', line, 1)[0].strip().lower()
                        # Normalize: Flask-CORS -> flask_cors
                        pkg_name = pkg_name.replace('-', '_')
                        installed_deps.add(pkg_name)
            except IOError as e:
                logger.warning(f"[DependencyHealer] Failed to read requirements.txt: {e}")
        
        # Scan all Python files for imports
        imported_modules: Set[str] = set()
        for py_file in backend_dir.rglob('*.py'):
            imports = self._extract_python_imports(py_file)
            imported_modules.update(imports)
        
        # Filter to find missing external packages
        missing: Set[str] = set()
        for module in imported_modules:
            # Get base module name
            base_module = module.split('.')[0].lower().replace('-', '_')
            
            # Skip stdlib and local modules
            if base_module in self.PYTHON_STDLIB:
                continue
            if base_module in self.LOCAL_PREFIXES:
                continue
            
            # Check if installed
            if base_module not in installed_deps:
                # Only flag if we know about this package
                if base_module in self.KNOWN_PYTHON_PACKAGES:
                    missing.add(base_module)
                    logger.debug(f"[DependencyHealer] Missing Python dep: {base_module}")
        
        return missing

    def _extract_python_imports(self, file_path: Path) -> Set[str]:
        """Extract import statements from a Python file."""
        imports: Set[str] = set()
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
                        
        except SyntaxError:
            # Fall back to regex for files with syntax errors
            try:
                import_pattern = re.compile(
                    r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))',
                    re.MULTILINE
                )
                for match in import_pattern.finditer(content):
                    module = match.group(1) or match.group(2)
                    if module:
                        imports.add(module)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"[DependencyHealer] Failed to parse {file_path}: {e}")
        
        return imports

    def _add_python_dependencies(self, requirements_path: Path, deps: Set[str], result: HealingResult) -> None:
        """Add missing Python dependencies to requirements.txt."""
        try:
            existing_content = ''
            if requirements_path.exists():
                existing_content = requirements_path.read_text(encoding='utf-8')
            
            # Parse existing packages
            existing_packages: Set[str] = set()
            for line in existing_content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    pkg_name = re.split(r'[<>=!~\[]', line, 1)[0].strip().lower()
                    existing_packages.add(pkg_name.replace('-', '_'))
            
            # Add new packages
            added = []
            new_lines = []
            for dep in sorted(deps):
                normalized = dep.replace('-', '_')
                if normalized not in existing_packages:
                    pkg_spec = self.KNOWN_PYTHON_PACKAGES.get(dep, dep)
                    new_lines.append(pkg_spec)
                    added.append(pkg_spec)
            
            if new_lines:
                # Append to requirements.txt
                with requirements_path.open('a', encoding='utf-8') as f:
                    if existing_content and not existing_content.endswith('\n'):
                        f.write('\n')
                    f.write('# Auto-added by DependencyHealer\n')
                    f.write('\n'.join(new_lines) + '\n')
                
                result.changes_made.append(f"Added Python dependencies: {', '.join(added)}")
                result.issues_fixed += len(added)
                logger.info(f"[DependencyHealer] Added Python deps: {', '.join(added)}")
                
        except Exception as e:
            result.errors.append(f"Failed to update requirements.txt: {e}")
            logger.error(f"[DependencyHealer] Failed to update requirements.txt: {e}")

    def _check_python_syntax(self, backend_dir: Path) -> List[str]:
        """Check Python files for syntax errors."""
        issues = []
        
        for py_file in backend_dir.rglob('*.py'):
            try:
                content = py_file.read_text(encoding='utf-8')
                ast.parse(content)
            except SyntaxError as e:
                rel_path = py_file.relative_to(backend_dir)
                issues.append(f"Syntax error in {rel_path} line {e.lineno}: {e.msg}")
            except Exception as e:
                rel_path = py_file.relative_to(backend_dir)
                issues.append(f"Parse error in {rel_path}: {str(e)}")
        
        return issues


# Singleton instance
_healer_instance: Optional[DependencyHealer] = None


def get_dependency_healer(auto_fix: bool = True) -> DependencyHealer:
    """Get or create the singleton DependencyHealer instance."""
    global _healer_instance
    if _healer_instance is None:
        _healer_instance = DependencyHealer(auto_fix=auto_fix)
    return _healer_instance


def heal_generated_app(app_dir: Path, auto_fix: bool = True) -> HealingResult:
    """
    Convenience function to heal a generated app.
    
    Args:
        app_dir: Path to the generated app directory
        auto_fix: Whether to automatically fix issues
        
    Returns:
        HealingResult with details of issues found and fixed
    """
    healer = get_dependency_healer(auto_fix=auto_fix)
    return healer.heal_app(app_dir)
