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
from typing import Any, Dict, List, Optional, Set, Tuple

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
        api_js_path = frontend_dir / 'src' / 'services' / 'api.js'
        
        if not src_dir.exists():
            logger.warning(f"[DependencyHealer] Frontend src/ not found: {src_dir}")
            return
        
        # 0. Fix JSX files with wrong .js extension (MUST run first - prevents Vite build failures)
        jsx_issues = self._find_jsx_extension_issues(src_dir)
        if jsx_issues:
            for issue in jsx_issues:
                result.frontend_issues.append(issue['message'])
                result.issues_found += 1
            
            if self.auto_fix:
                self._fix_jsx_extensions(jsx_issues, result)

        # 1. Fix common relative import path mistakes (e.g., ./services/* from pages)
        import_fix = self._fix_relative_import_paths(src_dir, auto_fix=self.auto_fix)
        for issue in import_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if import_fix['fixed_count'] > 0:
            result.issues_fixed += import_fix['fixed_count']
            result.changes_made.extend(import_fix['changes'])
        
        # 2. Scan for missing npm dependencies
        missing_deps = self._find_missing_npm_deps(src_dir, package_json_path)
        if missing_deps:
            for dep in missing_deps:
                result.frontend_issues.append(f"Missing npm dependency: {dep}")
                result.issues_found += 1
            
            if self.auto_fix:
                self._add_npm_dependencies(package_json_path, missing_deps, result)
        
        # 3. Check export patterns in components
        export_issues = self._check_frontend_exports(src_dir)
        if export_issues:
            for issue in export_issues:
                result.frontend_issues.append(issue['message'])
                result.issues_found += 1
            
            if self.auto_fix:
                self._fix_frontend_exports(export_issues, result)

        # 4. Ensure API exports referenced by pages exist (prevents Vite build failures)
        api_fix = self._ensure_api_exports(src_dir, api_js_path, auto_fix=self.auto_fix)
        for issue in api_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if api_fix['fixed_count'] > 0:
            result.issues_fixed += api_fix['fixed_count']
            result.changes_made.extend(api_fix['changes'])

    def _fix_relative_import_paths(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix common relative import path mistakes in frontend files."""
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0

        def resolve_module(base_dir: Path, rel_path: str) -> bool:
            candidate = (base_dir / rel_path).resolve()

            candidates = []
            if candidate.suffix:
                candidates.append(candidate)
            else:
                for ext in ('.js', '.jsx', '.ts', '.tsx', '.json'):
                    candidates.append(candidate.with_suffix(ext))
                for ext in ('.js', '.jsx', '.ts', '.tsx', '.json'):
                    candidates.append(candidate / f'index{ext}')

            return any(path.exists() for path in candidates)

        def normalize_to_src(import_path: str) -> Optional[Path]:
            parts = list(Path(import_path).as_posix().split('/'))
            while parts and parts[0] in ('.', '..'):
                parts.pop(0)
            if not parts:
                return None
            return src_dir / Path(*parts)

        import_pattern = re.compile(
            r"import\s+[^\n]+?\s+from\s+['\"](?P<path>[^'\"]+)['\"]"
        )

        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue

            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception:
                continue

            updated = False

            def replace(match: re.Match) -> str:
                nonlocal updated, fixed_count
                import_path = match.group('path')

                if not import_path.startswith('.'):
                    return match.group(0)

                file_dir = file_path.parent
                if resolve_module(file_dir, import_path):
                    return match.group(0)

                src_target = normalize_to_src(import_path)
                if src_target is None or not resolve_module(src_dir, src_target.relative_to(src_dir).as_posix()):
                    return match.group(0)

                new_rel = os.path.relpath(src_target, file_dir).replace('\\', '/')
                if not new_rel.startswith('.'):
                    new_rel = f'./{new_rel}'

                issues.append(
                    f"{file_path.relative_to(src_dir)}: fixed import '{import_path}' → '{new_rel}'"
                )

                if auto_fix:
                    updated = True
                    fixed_count += 1
                    return match.group(0).replace(import_path, new_rel)

                return match.group(0)

            new_content = import_pattern.sub(replace, content)

            if auto_fix and updated and new_content != content:
                try:
                    file_path.write_text(new_content, encoding='utf-8')
                    changes.append(f"Updated relative imports in {file_path.relative_to(src_dir)}")
                except Exception as e:
                    issues.append(f"Failed to update {file_path.name}: {e}")

        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

    def _find_jsx_extension_issues(self, src_dir: Path) -> List[Dict]:
        """Find .js files that contain JSX syntax and should be .jsx.
        
        Vite/Rollup requires JSX code to be in files with .jsx extension.
        This catches the common AI generation mistake of using .js for files
        containing React JSX syntax like <Component />.
        """
        issues = []
        
        # JSX pattern: matches typical JSX elements like <Component>, <div>, etc.
        # More comprehensive patterns to catch various JSX forms
        jsx_patterns = [
            re.compile(r'<[A-Z][a-zA-Z0-9]*[\s/>]'),           # <ComponentName or <ComponentName>
            re.compile(r'<[a-z]+[\s/>]'),                      # HTML elements: <div>, <span>, etc.
            re.compile(r'</[A-Za-z][a-zA-Z0-9]*>'),            # Closing tags: </Component>
            re.compile(r'<>\s*'),                              # Fragment: <>
            re.compile(r'</>\s*'),                             # Fragment closing: </>
            re.compile(r'\breturn\s*\(\s*<'),                  # return (<Element)
            re.compile(r'\breturn\s+<[A-Za-z]'),               # return <Element
        ]
        
        for js_file in src_dir.rglob('*.js'):
            # Skip node_modules and other irrelevant directories
            if 'node_modules' in str(js_file):
                continue
            
            try:
                content = js_file.read_text(encoding='utf-8')
                
                # Check for JSX patterns
                has_jsx = any(pattern.search(content) for pattern in jsx_patterns)
                
                if has_jsx:
                    # Double-check: remove comments, strings, and template literals
                    # to avoid false positives from HTML in strings
                    content_cleaned = content
                    
                    # Remove single-line comments
                    content_cleaned = re.sub(r'//.*$', '', content_cleaned, flags=re.MULTILINE)
                    # Remove multi-line comments
                    content_cleaned = re.sub(r'/\*.*?\*/', '', content_cleaned, flags=re.DOTALL)
                    # Remove template literals (backtick strings) - can contain HTML
                    content_cleaned = re.sub(r'`[^`]*`', '""', content_cleaned, flags=re.DOTALL)
                    # Remove regular strings - can contain HTML
                    content_cleaned = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', content_cleaned)
                    content_cleaned = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", content_cleaned)
                    
                    has_jsx_real = any(pattern.search(content_cleaned) for pattern in jsx_patterns)
                    
                    if has_jsx_real:
                        jsx_path = js_file.with_suffix('.jsx')
                        issues.append({
                            'file': js_file,
                            'new_file': jsx_path,
                            'message': f"File contains JSX but has .js extension: {js_file.relative_to(src_dir.parent)}"
                        })
                        logger.debug(f"[DependencyHealer] JSX in .js file: {js_file}")
                        
            except Exception as e:
                logger.debug(f"[DependencyHealer] Failed to check {js_file}: {e}")
        
        return issues
    
    def _fix_jsx_extensions(self, issues: List[Dict], result: HealingResult) -> None:
        """Rename .js files containing JSX to .jsx extension."""
        for issue in issues:
            old_path: Path = issue['file']
            new_path: Path = issue['new_file']
            
            try:
                # Check if new path already exists
                if new_path.exists():
                    logger.warning(
                        f"[DependencyHealer] Cannot rename {old_path.name} to {new_path.name}: "
                        f"target already exists"
                    )
                    result.errors.append(f"Cannot rename {old_path.name}: {new_path.name} already exists")
                    continue
                
                # Rename the file
                old_path.rename(new_path)
                result.changes_made.append(f"Renamed {old_path.name} → {new_path.name}")
                result.issues_fixed += 1
                logger.info(f"[DependencyHealer] Renamed {old_path.name} → {new_path.name}")
                
            except Exception as e:
                result.errors.append(f"Failed to rename {old_path.name}: {e}")
                logger.error(f"[DependencyHealer] Failed to rename {old_path}: {e}")

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

    def _ensure_api_exports(self, src_dir: Path, api_js_path: Path, auto_fix: bool) -> Dict[str, Any]:
        """Ensure functions imported from services/api.js are exported there."""
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0

        if not api_js_path.exists():
            return {'issues': issues, 'changes': changes, 'fixed_count': fixed_count}

        try:
            api_content = api_js_path.read_text(encoding='utf-8')
        except Exception as e:
            return {'issues': [f"Failed to read api.js: {e}"], 'changes': [], 'fixed_count': 0}

        content_modified = False

        # Remove invalid self-reexports that duplicate named exports (e.g. export { api } from './api')
        self_reexport_pattern = re.compile(
            r"^\s*export\s*\{[^}]*\}\s*from\s*['\"]\./api['\"];?\s*$",
            re.MULTILINE
        )
        if self_reexport_pattern.search(api_content):
            issues.append("api.js re-exports from './api' causing duplicate exports")
            if auto_fix:
                api_content = self_reexport_pattern.sub('', api_content).rstrip() + "\n"
                changes.append("Removed self-reexport from api.js")
                fixed_count += 1
                content_modified = True

        if content_modified and auto_fix:
            try:
                api_js_path.write_text(api_content, encoding='utf-8')
            except Exception as e:
                issues.append(f"Failed to write api.js: {e}")

        exported = set()
        for match in re.finditer(r'export\s+(?:const|function)\s+(\w+)', api_content):
            exported.add(match.group(1))

        def _collect_imports(file_path: Path) -> List[str]:
            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception:
                return []
            imports = []
            for match in re.finditer(
                r"import\s*\{([^}]+)\}\s*from\s*['\"](?:\.{1,2}/)*services/api['\"]",
                content
            ):
                names = match.group(1)
                for name in names.split(','):
                    clean = name.strip().split(' as ')[0]
                    if clean:
                        imports.append(clean)
            return imports

        wanted_admin = set()
        wanted_user = set()
        admin_path = src_dir / 'pages' / 'AdminPage.jsx'
        user_path = src_dir / 'pages' / 'UserPage.jsx'
        if admin_path.exists():
            wanted_admin.update(_collect_imports(admin_path))
        if user_path.exists():
            wanted_user.update(_collect_imports(user_path))

        wanted = wanted_admin | wanted_user

        missing = sorted(name for name in wanted if name not in exported)
        if not missing and not content_modified:
            return {'issues': issues, 'changes': changes, 'fixed_count': fixed_count}

        for name in missing:
            issues.append(f"api.js missing export for {name}")

        if auto_fix:
            additions = []
            for name in missing:
                is_admin = name in wanted_admin
                endpoint = self._infer_endpoint(name, is_admin=is_admin)
                additions.append(
                    f"export const {name} = (payload) => api.{endpoint['method']}('{endpoint['path']}', payload);"
                )
            api_content = api_content.rstrip() + "\n\n// Auto-added admin API exports\n" + "\n".join(additions) + "\n"
            try:
                api_js_path.write_text(api_content, encoding='utf-8')
                changes.append(f"Added {len(missing)} missing exports to api.js")
                fixed_count += len(missing)
            except Exception as e:
                issues.append(f"Failed to write api.js: {e}")

        return {'issues': issues, 'changes': changes, 'fixed_count': fixed_count}

    def _infer_endpoint(self, function_name: str, is_admin: bool) -> Dict[str, str]:
        """Infer a reasonable endpoint path for a missing API export."""
        name = function_name
        method = 'get'
        path = '/admin' if is_admin else ''

        # Determine method
        if re.search(r'^(create|add|post)', name, re.IGNORECASE):
            method = 'post'
        elif re.search(r'^(update|edit|put)', name, re.IGNORECASE):
            method = 'put'
        elif re.search(r'^(delete|remove)', name, re.IGNORECASE):
            method = 'delete'

        # Determine resource
        resource = None
        for candidate in ['todos', 'validations', 'conversions', 'items', 'stats']:
            if re.search(candidate, name, re.IGNORECASE):
                resource = candidate
                break

        if 'stats' in name.lower():
            path = '/admin/stats' if is_admin else '/stats'
            method = 'get'
        elif resource:
            prefix = '/admin' if is_admin else ''
            path = f"{prefix}/{resource}"

        if 'toggle' in name.lower():
            path = f"{path}/{{id}}/toggle"
            method = 'post'
        if 'bulk' in name.lower():
            path = f"{path}/bulk-delete"
            method = 'post'

        return {'method': method, 'path': path}

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

        # 2. Fix common backend route issues (imports, blueprint usage, model name mismatches)
        route_fix_summary = self._fix_backend_route_issues(backend_dir, auto_fix=self.auto_fix)
        for issue in route_fix_summary['issues']:
            result.backend_issues.append(issue)
            result.issues_found += 1
        if route_fix_summary['fixed_count'] > 0:
            result.issues_fixed += route_fix_summary['fixed_count']
            result.changes_made.extend(route_fix_summary['changes'])
        
        # 3. Check for Python syntax errors
        syntax_issues = self._check_python_syntax(backend_dir)
        if syntax_issues:
            for issue in syntax_issues:
                result.backend_issues.append(issue)
                result.issues_found += 1
            # Syntax errors can't be auto-fixed

    def _fix_backend_route_issues(self, backend_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Detect and optionally fix common backend route issues."""
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0

        routes_dir = backend_dir / 'routes'
        models_path = backend_dir / 'models.py'
        model_classes = self._extract_model_class_names(models_path)

        def maybe_write(path: Path, new_content: str, change_message: str) -> None:
            nonlocal fixed_count
            if not auto_fix:
                return
            try:
                if new_content != path.read_text(encoding='utf-8'):
                    path.write_text(new_content, encoding='utf-8')
                    changes.append(change_message)
                    fixed_count += 1
            except Exception as e:
                issues.append(f"Failed to update {path.name}: {e}")

        def ensure_import(content: str, import_line: str) -> str:
            if import_line in content:
                return content
            lines = content.splitlines()
            insert_at = 0
            for idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('#') or stripped == '':
                    continue
                if stripped.startswith('import ') or stripped.startswith('from '):
                    insert_at = idx + 1
                    continue
                break
            lines.insert(insert_at, import_line)
            return "\n".join(lines) + ("\n" if content.endswith("\n") else "")

        def has_imported_name(content: str, name: str) -> bool:
            pattern = re.compile(rf'^\s*from\s+[\w.]+\s+import\s+.*\b{re.escape(name)}\b', re.MULTILINE)
            if pattern.search(content):
                return True
            return bool(re.search(rf'^\s*import\s+.*\b{re.escape(name)}\b', content, flags=re.MULTILINE))

        # -------------------- routes/user.py --------------------
        user_path = routes_dir / 'user.py'
        if user_path.exists():
            try:
                content = user_path.read_text(encoding='utf-8')
                if ('@token_required' in content or 'token_required(' in content) and 'from routes.auth import token_required' not in content:
                    issues.append("routes/user.py missing token_required import")
                    content = ensure_import(content, 'from routes.auth import token_required')

                if 'user_bp' in content and 'from routes import user_bp' not in content:
                    issues.append("routes/user.py missing user_bp import")
                    content = ensure_import(content, 'from routes import user_bp')

                maybe_write(user_path, content, "Auto-fixed routes/user.py imports")
            except Exception as e:
                issues.append(f"Failed to inspect routes/user.py: {e}")

        # -------------------- routes/admin.py --------------------
        admin_path = routes_dir / 'admin.py'
        if admin_path.exists():
            try:
                content = admin_path.read_text(encoding='utf-8')

                if 'from .admin_bp import admin_bp' in content or 'from admin_bp import admin_bp' in content:
                    issues.append("routes/admin.py uses incorrect admin_bp import")
                    content = content.replace('from .admin_bp import admin_bp', 'from routes import admin_bp')
                    content = content.replace('from admin_bp import admin_bp', 'from routes import admin_bp')

                if ('@admin_required' in content or 'admin_required(' in content) and 'from routes.auth import admin_required' not in content:
                    issues.append("routes/admin.py missing admin_required import")
                    content = ensure_import(content, 'from routes.auth import admin_required')

                if 'admin_bp' in content and 'from routes import admin_bp' not in content:
                    issues.append("routes/admin.py missing admin_bp import")
                    content = ensure_import(content, 'from routes import admin_bp')

                if 'ShortUrl' in content and 'ShortUrl' not in model_classes and 'URL' in model_classes:
                    issues.append("routes/admin.py references ShortUrl but models define URL")
                    content = content.replace('ShortUrl', 'URL')

                maybe_write(admin_path, content, "Auto-fixed routes/admin.py imports/model references")
            except Exception as e:
                issues.append(f"Failed to inspect routes/admin.py: {e}")

        # -------------------- routes/auth.py --------------------
        auth_path = routes_dir / 'auth.py'
        if auth_path.exists():
            try:
                content = auth_path.read_text(encoding='utf-8')

                if ('datetime.' in content or 'timedelta' in content) and 'from datetime import datetime, timedelta' not in content:
                    issues.append("routes/auth.py missing datetime import")
                    content = ensure_import(content, 'from datetime import datetime, timedelta')

                if 'generate_password_hash' in content and 'from werkzeug.security import generate_password_hash' not in content:
                    issues.append("routes/auth.py missing generate_password_hash import")
                    content = ensure_import(content, 'from werkzeug.security import generate_password_hash')

                if 'jwt.' in content and 'import jwt' not in content:
                    issues.append("routes/auth.py missing jwt import")
                    content = ensure_import(content, 'import jwt')

                if 'User' in content and not has_imported_name(content, 'User'):
                    issues.append("routes/auth.py missing User import")
                    content = ensure_import(content, 'from models import User')

                maybe_write(auth_path, content, "Auto-fixed routes/auth.py imports")
            except Exception as e:
                issues.append(f"Failed to inspect routes/auth.py: {e}")

        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

    def _extract_model_class_names(self, models_path: Path) -> List[str]:
        """Extract model class names from models.py."""
        if not models_path.exists():
            return []
        try:
            content = models_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            class_names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_names.append(node.name)
            return class_names
        except Exception:
            # Fallback regex
            try:
                content = models_path.read_text(encoding='utf-8')
                return re.findall(r'class\s+(\w+)\s*\(.*?\):', content)
            except Exception:
                return []

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
