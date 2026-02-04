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

        # Validation
        'validators': 'validators==0.22.0',
        
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
        
        # 5. Fix icon import issues (FA hallucinations, stray heroicons)
        icon_fix = self._fix_icon_imports(src_dir, auto_fix=self.auto_fix)
        for issue in icon_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if icon_fix['fixed_count'] > 0:
            result.issues_fixed += icon_fix['fixed_count']
            result.changes_made.extend(icon_fix['changes'])

        # 6. Fix react-hot-toast usage (ToastContainer -> Toaster)
        toast_fix = self._fix_react_hot_toast_usage(src_dir, auto_fix=self.auto_fix)
        for issue in toast_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if toast_fix['fixed_count'] > 0:
            result.issues_fixed += toast_fix['fixed_count']
            result.changes_made.extend(toast_fix['changes'])

        # 7. Fix named vs default import mismatches for local components
        import_mismatch_fix = self._fix_import_export_mismatches(src_dir, auto_fix=self.auto_fix)
        for issue in import_mismatch_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if import_mismatch_fix['fixed_count'] > 0:
            result.issues_fixed += import_mismatch_fix['fixed_count']
            result.changes_made.extend(import_mismatch_fix['changes'])

        # 8. Fix missing React Router imports (e.g., Navigate, Link)
        router_fix = self._fix_missing_router_imports(src_dir, auto_fix=self.auto_fix)
        for issue in router_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if router_fix['fixed_count'] > 0:
            result.issues_fixed += router_fix['fixed_count']
            result.changes_made.extend(router_fix['changes'])

        # 9. Fix name collisions between local components and Router components (e.g., function Routes)
        collision_fix = self._fix_router_name_collisions(src_dir, auto_fix=self.auto_fix)
        for issue in collision_fix['issues']:
            result.frontend_issues.append(issue)
            result.issues_found += 1
        if collision_fix['fixed_count'] > 0:
            result.issues_fixed += collision_fix['fixed_count']
            result.changes_made.extend(collision_fix['changes'])

    def _fix_missing_router_imports(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix missing react-router-dom imports.
        
        LLMs often use components like Navigate, Link, or hooks like useNavigate
        without adding them to the react-router-dom import block.
        """
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0
        
        router_components = {
            'Navigate', 'Link', 'NavLink', 'Route', 'Routes', 'BrowserRouter',
            'useNavigate', 'useParams', 'useLocation', 'useSearchParams', 'Outlet'
        }
        
        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
                original_content = content
                
                # Find the react-router-dom import line
                router_import_match = re.search(
                    r"import\s*\{([^}]+)\}\s*from\s*['\"]react-router-dom['\"]",
                    content
                )
                
                if not router_import_match:
                    continue
                
                existing_imports = {n.strip() for n in router_import_match.group(1).split(',')}
                missing_imports = set()
                
                for comp in router_components:
                    if comp not in existing_imports:
                        # Check if it's used in the code (as a JSX tag or hook call)
                        if re.search(rf'<{comp}\b|\b{comp}\(', content):
                            missing_imports.add(comp)
                
                if missing_imports:
                    issues.append(
                        f"{file_path.relative_to(src_dir.parent)}: missing react-router-dom imports: {', '.join(missing_imports)}"
                    )
                    
                    if auto_fix:
                        new_imports = sorted(existing_imports | missing_imports)
                        new_import_line = f"import {{ {', '.join(new_imports)} }} from 'react-router-dom'"
                        content = content.replace(router_import_match.group(0), new_import_line)
                        
                        if content != original_content:
                            file_path.write_text(content, encoding='utf-8')
                            changes.append(f"Added missing Router imports in {file_path.relative_to(src_dir.parent)}")
                            fixed_count += 1
                            logger.info(f"[DependencyHealer] Fixed Router imports in {file_path.name}")
                            
            except Exception as e:
                logger.debug(f"[DependencyHealer] Failed to process {file_path}: {e}")
        
        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

    def _fix_router_name_collisions(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix name collisions between local components/functions and react-router-dom.
        
        Example: function Routes() { ... } clashing with import { Routes } from 'react-router-dom'.
        """
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0
        
        collisions_to_fix = {
            'Routes': 'AppRoutes',
            'Link': 'AppLink',
        }
        
        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
                original_content = content
                
                # Check if react-router-dom is imported
                if "import { " not in content or "'react-router-dom'" not in content:
                    continue
                
                file_changed = False
                for old_name, new_name in collisions_to_fix.items():
                    # Look for "function Routes" or "const Routes ="
                    if re.search(rf'\b(function|const|let|var)\s+{old_name}\s*[(=]', content):
                        issues.append(
                            f"{file_path.relative_to(src_dir.parent)}: local variable '{old_name}' clashes with Router import"
                        )
                        
                        if auto_fix:
                            # Rename the definition
                            content = re.sub(rf'\b(function|const|let|var)\s+{old_name}\b', rf'\1 {new_name}', content)
                            # Rename the usage as a component (JSX) - but ONLY if it's likely the local one
                            # This is tricky, but usually the local one is what the LLM meant to use for its own logic.
                            # However, in the case of <Routes>, the inner one is usually the Router one.
                            # But if the LLM named its OWN component "Routes", it probably wants to use it as <Routes />
                            # In app1.jkx, it defines `function Routes` and then returns `<div ...><Routes>...</Routes></div>`
                            # Wait, if it renames the definition to `AppRoutes`, it should probably rename the outer usage too.
                            
                            # Let's be safer: rename the definition and ALL usages, 
                            # then the import-healer will add the Router one back if needed.
                            # But wait, the Router one is ALREADY imported.
                            
                            # Specific fix for the "function Routes" case:
                            # 1. Rename `function Routes` to `function AppRoutes`
                            # 2. Rename `<Routes` to `<AppRoutes` and `</Routes>` to `</AppRoutes>`
                            # UNLESS it's the one wrapping everything.
                            
                            content = content.replace(f'<{old_name}', f'<{new_name}')
                            content = content.replace(f'</{old_name}>', f'</{new_name}>')
                            
                            file_changed = True
                
                if auto_fix and file_changed and content != original_content:
                    file_path.write_text(content, encoding='utf-8')
                    changes.append(f"Fixed Router name collisions in {file_path.relative_to(src_dir.parent)}")
                    fixed_count += 1
                    logger.info(f"[DependencyHealer] Fixed name collisions in {file_path.name}")
                            
            except Exception as e:
                logger.debug(f"[DependencyHealer] Failed to process {file_path}: {e}")
        
        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

    def _fix_relative_import_paths(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix common relative import path mistakes in frontend files.
        
        LLMs commonly make these mistakes:
        - From pages/AdminPage.jsx: `from './services/api'` instead of `from '../services/api'`
        - From pages/UserPage.jsx: `from './hooks/useAuth'` instead of `from '../hooks/useAuth'`
        """
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0

        def resolve_module(base_dir: Path, rel_path: str) -> bool:
            """Check if a relative import path resolves to an actual file.
            
            Handles both direct file imports and index file imports.
            For example, if rel_path is './utils', it will check for:
            - ./utils (with various extensions)
            - ./utils/index.js, ./utils/index.jsx, etc.
            """
            candidate = (base_dir / rel_path).resolve()

            candidates = []
            if candidate.suffix:
                # Direct file reference - check as-is
                candidates.append(candidate)
            else:
                # Directory or extensionless import - try multiple extensions
                for ext in ('.js', '.jsx', '.ts', '.tsx', '.json'):
                    candidates.append(candidate.with_suffix(ext))
                # Also check for index files in directories
                for ext in ('.js', '.jsx', '.ts', '.tsx', '.json'):
                    candidates.append(candidate / f'index{ext}')

            return any(path.exists() for path in candidates)

        def normalize_to_src(import_path: str) -> Optional[Path]:
            """Convert a relative import path to an absolute path relative to src/.
            
            Strips leading ./ and ../ to get the path within the src directory.
            Used to correlate imports with the export_map built from src files.
            """
            parts = list(Path(import_path).as_posix().split('/'))
            while parts and parts[0] in ('.', '..'):
                parts.pop(0)
            if not parts:
                return None
            return src_dir / Path(*parts)
        
        # Known LLM mistake patterns: (wrong_pattern, correct_pattern_template)
        # These are imports from files in subdirectories that should use ../
        common_mistakes = {
            # From pages/* files importing ./services/* should be ../services/*
            './services/': '../services/',
            './hooks/': '../hooks/',
            './components/': '../components/',
            './utils/': '../utils/',
        }

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
            
            # Determine if this file is in a subdirectory of src (pages/, components/, etc.)
            # This affects which import patterns we consider as "common mistakes"
            try:
                rel_to_src = file_path.parent.relative_to(src_dir)
                is_in_subdir = len(rel_to_src.parts) > 0 and rel_to_src.parts[0] in {'pages', 'components', 'hooks', 'utils'}
            except ValueError:
                is_in_subdir = False

            updated = False
            original_content = content

            def replace(match: re.Match) -> str:
                """Replace function called for each import match.
                
                Performs two-stage import resolution:
                1. Quick fix for known LLM mistakes (pattern-based)
                2. Fallback resolution for other import issues
                """
                nonlocal updated, fixed_count
                import_path = match.group('path')

                if not import_path.startswith('.'):
                    # Skip absolute imports (npm packages, etc.)
                    return match.group(0)

                file_dir = file_path.parent
                
                # Quick fix for common LLM mistakes when in subdirectory
                # These are high-confidence fixes based on observed patterns
                if is_in_subdir:
                    for wrong, correct in common_mistakes.items():
                        if import_path.startswith(wrong):
                            # Verify the corrected path actually resolves before applying
                            corrected = import_path.replace(wrong, correct, 1)
                            if resolve_module(file_dir, corrected):
                                issues.append(
                                    f"{file_path.relative_to(src_dir)}: fixed import '{import_path}' → '{corrected}'"
                                )
                                if auto_fix:
                                    updated = True
                                    fixed_count += 1
                                    return match.group(0).replace(import_path, corrected)
                                return match.group(0)
                
                # Original resolution logic for other cases
                # Check if current import path resolves from file's directory
                if resolve_module(file_dir, import_path):
                    return match.group(0)

                # If not, try to find the correct relative path from src/
                src_target = normalize_to_src(import_path)
                if src_target is None or not resolve_module(src_dir, src_target.relative_to(src_dir).as_posix()):
                    return match.group(0)

                # Calculate correct relative path from current file to target
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

            if auto_fix and updated and new_content != original_content:
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

    def _fix_icon_imports(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix common icon import issues in generated frontend code.

        Handles:
        1. Font Awesome hallucinated names -> correct FA names
        2. Heroicons imports -> stripped (not in package.json)
        """
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0

        # Common FA icon name hallucinations -> correct FA 6 names
        fa_fixes = {
            'faAlertCircle': 'faCircleExclamation',
            'faTasks': 'faListCheck',
            'faBarChart': 'faChartBar',
            'faDotCircle': 'faCircleDot',
            'faShield': 'faShieldHalved',
            'faZap': 'faBolt',
            'faMousePointer': 'faArrowPointer',
            'faCalendarAlt': 'faCalendarDays',
            'faHistory': 'faClockRotateLeft',
            'faAlertTriangle': 'faTriangleExclamation',
            'faKanban': 'faColumns',
            'faArrowLeftRight': 'faArrowsLeftRight',
            'faArrowUpDown': 'faArrowsUpDown',
            'faExchange': 'faArrowRightArrowLeft',
            'faExchangeAlt': 'faArrowRightArrowLeft',
            'faRandom': 'faShuffle',
            'faCircleNotch': 'faSpinner',
        }

        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue

            try:
                content = file_path.read_text(encoding='utf-8')
                original_content = content
                file_changes: List[str] = []

                # 1. Fix FA hallucinations
                for invalid, valid in fa_fixes.items():
                    if invalid in content:
                        content = content.replace(invalid, valid)
                        file_changes.append(f"{invalid} → {valid}")

                # 2. Strip heroicons imports (package not in dependencies)
                if '@heroicons/react' in content:
                    content = re.sub(
                        r'^import\s+\{[^}]*\}\s+from\s+[\'"]@heroicons/react[^\'"]*[\'"];?\s*$',
                        '// [auto-removed: heroicons not available]',
                        content, flags=re.MULTILINE
                    )
                    file_changes.append("stripped heroicons imports")

                if file_changes:
                    rel = file_path.relative_to(src_dir.parent)
                    for ch in file_changes:
                        issues.append(f"{rel}: {ch}")

                    if auto_fix and content != original_content:
                        file_path.write_text(content, encoding='utf-8')
                        changes.append(f"Fixed icon imports in {rel}")
                        fixed_count += 1
                        logger.info(f"[DependencyHealer] Fixed icon imports in {file_path.name}: {', '.join(file_changes)}")

            except Exception as e:
                logger.debug(f"[DependencyHealer] Failed to process {file_path}: {e}")

        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

    def _fix_react_hot_toast_usage(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix common react-hot-toast import mistakes.
        
        LLMs often confuse react-hot-toast with react-toastify:
        - Wrong: import { ToastContainer } from 'react-hot-toast'
        - Right: import { Toaster } from 'react-hot-toast'
        
        And in JSX:
        - Wrong: <ToastContainer />
        - Right: <Toaster />
        """
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0
        
        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
                original_content = content
                file_changed = False
                
                # Check for wrong import: ToastContainer from react-hot-toast
                if 'react-hot-toast' in content and 'ToastContainer' in content:
                    issues.append(
                        f"{file_path.relative_to(src_dir.parent)}: ToastContainer should be Toaster for react-hot-toast"
                    )
                    if auto_fix:
                        # Fix import statement
                        content = re.sub(
                            r'(\bimport\s*\{[^}]*)\bToastContainer\b([^}]*\}\s*from\s*[\'"]react-hot-toast[\'"])',
                            r'\1Toaster\2',
                            content
                        )
                        # Fix JSX usage
                        content = re.sub(r'<ToastContainer(\s*/?>|\s+[^>]*/?>)', r'<Toaster\1', content)
                        file_changed = True
                
                if auto_fix and file_changed and content != original_content:
                    file_path.write_text(content, encoding='utf-8')
                    changes.append(f"Fixed react-hot-toast imports in {file_path.relative_to(src_dir.parent)}")
                    fixed_count += 1
                    logger.info(f"[DependencyHealer] Fixed react-hot-toast in {file_path.name}")
                    
            except Exception as e:
                logger.debug(f"[DependencyHealer] Failed to process {file_path}: {e}")
        
        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

    def _fix_import_export_mismatches(self, src_dir: Path, auto_fix: bool) -> Dict[str, Any]:
        """Fix named import vs default export mismatches for local components.
        
        LLMs often mix up import styles:
        - File has: export default Spinner
        - Import uses: import { Spinner } from './Spinner'  (wrong)
        - Should be: import Spinner from './Spinner'  (correct)
        
        Or vice versa:
        - File has: export const Spinner = ...
        - Import uses: import Spinner from './Spinner'  (wrong)
        - Should be: import { Spinner } from './Spinner'  (correct)
        """
        issues: List[str] = []
        changes: List[str] = []
        fixed_count = 0
        
        # Build a map of local files and their export types
        # export_map[relative_path] = {'default': 'ComponentName' or None, 'named': ['export1', 'export2']}
        export_map: Dict[str, Dict[str, Any]] = {}
        
        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
                rel_path = file_path.relative_to(src_dir).as_posix()  # Use forward slashes
                
                exports = {'default': None, 'named': []}
                
                # Find default exports
                # export default ComponentName
                default_match = re.search(r'export\s+default\s+(?:function\s+)?(\w+)', content)
                if default_match:
                    exports['default'] = default_match.group(1)
                
                # Find named exports
                # export const/function/class Name
                for match in re.finditer(r'export\s+(?:const|let|var|function|class)\s+(\w+)', content):
                    exports['named'].append(match.group(1))
                
                # export { Name1, Name2 }
                for match in re.finditer(r'export\s*\{([^}]+)\}', content):
                    names = [n.strip().split(' as ')[0].strip() for n in match.group(1).split(',')]
                    exports['named'].extend(names)
                
                export_map[str(rel_path)] = exports
                
            except Exception:
                continue
        
        # Now scan imports and check for mismatches
        import_pattern = re.compile(
            r"import\s+(?:"
            r"(\w+)\s+from\s*['\"]([^'\"]+)['\"]"  # default import: import Name from './path'
            r"|"
            r"\{\s*([^}]+)\s*\}\s+from\s*['\"]([^'\"]+)['\"]"  # named import: import { Name } from './path'
            r")"
        )
        
        for file_path in src_dir.rglob('*'):
            if file_path.suffix not in {'.js', '.jsx', '.ts', '.tsx'}:
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
                original_content = content
                file_changed = False
                
                for match in import_pattern.finditer(content):
                    default_import = match.group(1)
                    default_path = match.group(2)
                    named_imports_str = match.group(3)
                    named_path = match.group(4)
                    
                    import_path = default_path or named_path
                    
                    # Only check local imports
                    if not import_path or not import_path.startswith('.'):
                        continue
                    
                    # Resolve the import path to a file
                    base_dir = file_path.parent
                    resolved_rel = None
                    
                    for ext in ['', '.js', '.jsx', '.ts', '.tsx']:
                        candidate = (base_dir / (import_path + ext)).resolve()
                        try:
                            candidate_rel = candidate.relative_to(src_dir).as_posix()
                            if candidate_rel in export_map:
                                resolved_rel = candidate_rel
                                break
                        except ValueError:
                            continue
                    
                    # Also try index files
                    if not resolved_rel:
                        for ext in ['.js', '.jsx', '.ts', '.tsx']:
                            candidate = (base_dir / import_path / f'index{ext}').resolve()
                            try:
                                candidate_rel = candidate.relative_to(src_dir).as_posix()
                                if candidate_rel in export_map:
                                    resolved_rel = candidate_rel
                                    break
                            except ValueError:
                                continue
                    
                    if not resolved_rel:
                        continue
                    
                    exports = export_map[resolved_rel]
                    
                    # Check for named import when file has default export
                    if named_imports_str and exports['default']:
                        named_imports = [n.strip() for n in named_imports_str.split(',')]
                        for name in named_imports:
                            name = name.split(' as ')[0].strip()
                            if name == exports['default'] and name not in exports['named']:
                                # This is a mismatch: named import of a default export
                                issues.append(
                                    f"{file_path.relative_to(src_dir)}: '{name}' has default export, use 'import {name}' not '{{  {name} }}'"
                                )
                                if auto_fix:
                                    # Fix: import { Name } from './path' -> import Name from './path'
                                    old_import = match.group(0)
                                    new_import = f"import {name} from '{named_path}'"
                                    content = content.replace(old_import, new_import)
                                    file_changed = True
                
                if auto_fix and file_changed and content != original_content:
                    file_path.write_text(content, encoding='utf-8')
                    changes.append(f"Fixed import/export mismatch in {file_path.relative_to(src_dir)}")
                    fixed_count += 1
                    logger.info(f"[DependencyHealer] Fixed import mismatch in {file_path.name}")
                    
            except Exception as e:
                logger.debug(f"[DependencyHealer] Failed to process {file_path}: {e}")
        
        return {
            'issues': issues,
            'changes': changes,
            'fixed_count': fixed_count,
        }

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
        """Ensure functions imported from services/api.js are exported there.
        
        This method prevents Vite build failures by ensuring that any API functions
        imported by pages (like AdminPage.jsx, UserPage.jsx) are actually exported
        from the services/api.js file. If missing, it auto-generates reasonable
        API function stubs based on function naming conventions.
        """
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
        # These cause "duplicate export" errors in ES modules
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

        # Find all currently exported functions in api.js
        exported = set()
        for match in re.finditer(r'export\s+(?:const|function)\s+(\w+)', api_content):
            exported.add(match.group(1))

        def _collect_imports(file_path: Path) -> List[str]:
            """Extract API function names imported from services/api.js in a page file."""
            try:
                content = file_path.read_text(encoding='utf-8')
            except Exception:
                return []
            imports = []
            # Match: import { functionName, otherFunc } from '../services/api'
            # Also matches: import { func } from '../../services/api' etc.
            for match in re.finditer(
                r"import\s*\{([^}]+)\}\s*from\s*['\"](?:\.{1,2}/)*services/api['\"]",
                content
            ):
                names = match.group(1)
                for name in names.split(','):
                    clean = name.strip().split(' as ')[0]  # Handle 'func as alias'
                    if clean:
                        imports.append(clean)
            return imports

        # Collect API functions needed by AdminPage and UserPage
        wanted_admin = set()
        wanted_user = set()
        admin_path = src_dir / 'pages' / 'AdminPage.jsx'
        user_path = src_dir / 'pages' / 'UserPage.jsx'
        if admin_path.exists():
            wanted_admin.update(_collect_imports(admin_path))
        if user_path.exists():
            wanted_user.update(_collect_imports(user_path))

        wanted = wanted_admin | wanted_user

        # Find missing exports
        missing = sorted(name for name in wanted if name not in exported)
        if not missing and not content_modified:
            return {'issues': issues, 'changes': changes, 'fixed_count': fixed_count}

        for name in missing:
            issues.append(f"api.js missing export for {name}")

        if auto_fix:
            additions = []
            for name in missing:
                # Infer API endpoint details from function name
                is_admin = name in wanted_admin
                endpoint = self._infer_endpoint(name, is_admin=is_admin)
                # Generate: export const functionName = (payload) => api.method('path', payload);
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
        """Infer a reasonable endpoint path for a missing API export.
        
        Uses naming conventions to guess the HTTP method and URL path:
        - Function names starting with 'create', 'add', 'post' → POST method
        - Names with 'update', 'edit', 'put' → PUT method  
        - Names with 'delete', 'remove' → DELETE method
        - Others default to GET
        
        Resource detection looks for keywords like 'todos', 'validations', etc.
        Special cases for 'stats' (always GET) and 'toggle'/'bulk' operations.
        """
        name = function_name
        method = 'get'  # Default HTTP method
        path = '/admin' if is_admin else ''  # Base path with admin prefix if needed

        # Determine HTTP method from function name prefixes
        if re.search(r'^(create|add|post)', name, re.IGNORECASE):
            method = 'post'
        elif re.search(r'^(update|edit|put)', name, re.IGNORECASE):
            method = 'put'
        elif re.search(r'^(delete|remove)', name, re.IGNORECASE):
            method = 'delete'

        # Determine resource type from function name keywords
        resource = None
        for candidate in ['todos', 'validations', 'conversions', 'items', 'stats']:
            if re.search(candidate, name, re.IGNORECASE):
                resource = candidate
                break

        # Special handling for stats (always admin/user stats endpoint)
        if 'stats' in name.lower():
            path = '/admin/stats' if is_admin else '/stats'
            method = 'get'  # Stats are always GET requests
        elif resource:
            # Standard resource endpoint: /admin/{resource} or /{resource}
            prefix = '/admin' if is_admin else ''
            path = f"{prefix}/{resource}"

        # Special path modifications for specific operation types
        if 'toggle' in name.lower():
            # Toggle operations: /resource/{id}/toggle
            path = f"{path}/{{id}}/toggle"
            method = 'post'  # Toggles are typically POST
        if 'bulk' in name.lower():
            # Bulk operations: /resource/bulk-delete
            path = f"{path}/bulk-delete"
            method = 'post'  # Bulk ops are typically POST

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
