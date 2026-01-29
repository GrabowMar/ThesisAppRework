"""Code Merger
=============

Merges generated code into the scaffolded app structure.
Simple file writing based on annotated code blocks.
"""

import ast
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.services.dependency_healer import DependencyHealer

logger = logging.getLogger(__name__)


class CodeMerger:
    """Merges generated code into app directory.
    
    Single-file mode:
    - backend → app.py only
    - frontend → App.jsx only
    
    Parses annotated code blocks like:
    ```python:app.py
    ```jsx:App.jsx
    """
    
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.backend_dir = app_dir / 'backend'
        self.frontend_dir = app_dir / 'frontend'
        self._stdlib_modules = DependencyHealer.PYTHON_STDLIB
        self._local_prefixes = DependencyHealer.LOCAL_PREFIXES
        self._package_version_map = DependencyHealer.KNOWN_PYTHON_PACKAGES
    
    def merge(self, code: Dict[str, str]) -> Dict[str, Path]:
        """Merge generated code into app directory.
        
        Args:
            code: Dict with 'backend' and 'frontend' raw LLM responses
            
        Returns:
            Dict mapping file type to written path
        """
        written_files = {}
        
        # Process backend
        if 'backend' in code and code['backend'].strip():
            logger.info("Processing backend code...")
            backend_files = self._process_backend(code['backend'])
            written_files.update(backend_files)
        else:
            logger.warning("No backend code found in response")
        
        # Process frontend
        if 'frontend' in code and code['frontend'].strip():
            logger.info("Processing frontend code...")
            frontend_files = self._process_frontend(code['frontend'])
            written_files.update(frontend_files)
        else:
            logger.warning("No frontend code found in response")
        
        logger.info(f"Merged {len(written_files)} files: {', '.join(written_files.keys())}")
        return written_files
    
    def _extract_code_blocks(self, content: str) -> List[Dict[str, str]]:
        """Extract all code blocks with annotations.
        
        Supports:
        - ```python:filename.py
        - ```jsx:pages/Component.jsx
        - ```javascript:services/api.js
        """
        blocks = []
        pattern = re.compile(
            r"```(?P<lang>[a-zA-Z0-9_+\.-]+)?(?:[ \t]*[: ]?[ \t]*(?P<filename>[^\n\r`]+))?\s*[\r\n]+(.*?)```",
            re.DOTALL
        )
        
        for match in pattern.finditer(content or ""):
            lang = (match.group('lang') or '').strip().lower()
            filename = (match.group('filename') or '').strip()
            code = (match.group(3) or '').strip()
            
            if code:
                blocks.append({
                    'language': lang,
                    'filename': filename,
                    'code': code
                })
        
        return blocks
    
    def _process_backend(self, raw_content: str) -> Dict[str, Path]:
        """Process backend code blocks - merges ALL Python code into app.py.

        Even if the LLM generates multiple files (models.py, routes/*.py),
        we merge everything into a single app.py for the single-file architecture.
        """
        written = {}
        blocks = self._extract_code_blocks(raw_content)

        # Fallback for models that don't use code blocks
        if not blocks and self._looks_like_python(raw_content):
            logger.info("No code blocks found, but content looks like Python. Using raw content.")
            blocks = [{
                'language': 'python',
                'filename': 'app.py',
                'code': raw_content.strip()
            }]

        # Collect all Python code blocks
        python_blocks = []
        for block in blocks:
            lang = (block['language'] or '').strip().lower()
            filename = (block['filename'] or '').strip()
            code = block['code']
            
            if not filename and lang.endswith('.py'):
                filename = lang
                lang = 'python'
            
            if not lang and filename.lower().endswith('.py'):
                lang = 'python'

            # Handle requirements block
            if lang == 'requirements' or (filename and 'requirements' in filename.lower()):
                self._merge_requirements(code)
                continue

            if lang == 'python':
                python_blocks.append({
                    'filename': filename or 'app.py',
                    'code': code
                })

        # IMPROVED FALLBACK: If no Python blocks found, but content looks like Python
        if not python_blocks and self._looks_like_python(raw_content):
            logger.info("No Python code blocks found, but content looks like Python. Attempting fallback extraction.")
            
            # If we found OTHER blocks (e.g. requirements), strip them out to isolate the code
            clean_content = raw_content
            if blocks:
                pattern = re.compile(
                    r"```(?P<lang>[a-zA-Z0-9_+\.-]+)?(?:[ \t]*[: ]?[ \t]*(?P<filename>[^\n\r`]+))?\s*[\r\n]+(.*?)```",
                    re.DOTALL
                )
                clean_content = pattern.sub('', raw_content).strip()
            
            # If the remaining content still looks like Python, use it
            if self._looks_like_python(clean_content):
                logger.info("Fallback successful: Using remaining content as app.py")
                python_blocks = [{
                    'filename': 'app.py',
                    'code': clean_content.strip()
                }]

        if not python_blocks:
            logger.warning("No Python code blocks found in backend response")
            return written

        # Check if we have a single app.py block
        app_blocks = [b for b in python_blocks
                      if b['filename'].lower().rstrip('.py') in ('app', 'main', '')]

        if len(python_blocks) == 1:
            # Single file case - use as-is
            code = python_blocks[0]['code']
        elif app_blocks and len(app_blocks) == 1 and len(python_blocks) <= 2:
            # Main app.py with maybe one helper - use app.py
            code = app_blocks[0]['code']
        else:
            # Multiple files case - merge into single app.py
            logger.info(f"Merging {len(python_blocks)} Python files into app.py")
            code = self._merge_python_files(python_blocks)

        # Write the merged app.py
        target_path = self.backend_dir / 'app.py'
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(code, encoding='utf-8')
        written['backend_app'] = target_path
        logger.info(f"✓ Wrote backend/app.py ({len(code)} chars)")

        # Infer and update missing dependencies in requirements.txt
        inferred_packages = self._infer_backend_dependencies(code)
        if inferred_packages:
            self._update_backend_requirements(inferred_packages)

        return written

    def _merge_python_files(self, blocks: List[Dict[str, str]]) -> str:
        """Merge multiple Python code blocks into a single app.py file.

        Strategy:
        1. Collect all imports from all files
        2. Collect model classes
        3. Collect route functions
        4. Reassemble in correct order
        """
        all_imports = set()
        model_code = []
        route_code = []
        other_code = []
        main_code = []

        import_pattern = re.compile(r'^(?:from\s+\S+\s+)?import\s+.+$', re.MULTILINE)

        for block in blocks:
            code = block['code']
            filename = block['filename'].lower()

            # Extract imports - collect all import statements from each file
            # Skip relative imports that won't work in single-file architecture
            for match in import_pattern.finditer(code):
                import_line = match.group().strip()
                # Skip relative imports that won't work in single file
                if not import_line.startswith('from .') and \
                   'from routes' not in import_line and \
                   'from models' not in import_line:
                    all_imports.add(import_line)

            # Remove imports from code for further processing
            code_without_imports = import_pattern.sub('', code).strip()

            # Categorize code blocks by filename patterns to organize the merged file
            if 'model' in filename:
                model_code.append(f"# From {block['filename']}\n{code_without_imports}")
            elif 'route' in filename or 'api' in filename:
                route_code.append(f"# From {block['filename']}\n{code_without_imports}")
            elif filename.rstrip('.py') in ('app', 'main', ''):
                main_code.append(code_without_imports)
            else:
                other_code.append(f"# From {block['filename']}\n{code_without_imports}")

        # Build merged file with proper organization
        parts = []

        # Standard imports first
        parts.append("# Merged from multiple generated files into single app.py")
        parts.append("")

        # Sort and add imports - standard library first, then third-party
        sorted_imports = sorted(all_imports, key=lambda x: (not x.startswith('import'), x.lower()))
        parts.extend(sorted_imports)
        parts.append("")

        # Add model code
        if model_code:
            parts.append("# " + "=" * 70)
            parts.append("# MODELS")
            parts.append("# " + "=" * 70)
            parts.extend(model_code)
            parts.append("")

        # Add other code (helpers, decorators, etc.)
        if other_code:
            parts.append("# " + "=" * 70)
            parts.append("# HELPERS")
            parts.append("# " + "=" * 70)
            parts.extend(other_code)
            parts.append("")

        # Add route code
        if route_code:
            parts.append("# " + "=" * 70)
            parts.append("# ROUTES")
            parts.append("# " + "=" * 70)
            parts.extend(route_code)
            parts.append("")

        # Add main code
        if main_code:
            parts.append("# " + "=" * 70)
            parts.append("# MAIN")
            parts.append("# " + "=" * 70)
            parts.extend(main_code)

        return '\n'.join(parts)

    def _infer_backend_dependencies(self, code: str) -> Set[str]:
        """Infer third-party packages from generated backend code."""
        modules: Set[str] = set()
        try:
            tree = ast.parse(code or '')
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        modules.add((alias.name or '').split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        modules.add(node.module.split('.')[0])
        except SyntaxError:
            logger.debug("AST parsing failed for dependency inference; falling back to regex")
            for match in re.finditer(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", code or '', re.MULTILINE):
                module = match.group(1) or match.group(2) or ''
                if module:
                    modules.add(module.split('.')[0])

        packages: Set[str] = set()
        for module in modules:
            normalized = (module or '').lower()
            if not normalized or normalized in self._stdlib_modules or normalized in self._local_prefixes:
                continue
            packages.add(self._package_version_map.get(normalized, module.replace('_', '-')))

        return packages

    def _update_backend_requirements(self, packages: Set[str]) -> None:
        """Append inferred packages to backend/requirements.txt if missing."""
        if not packages:
            return

        requirements_path = self.backend_dir / 'requirements.txt'
        if not requirements_path.exists():
            logger.warning("Backend requirements.txt missing at %s", requirements_path)
            return

        try:
            original_content = requirements_path.read_text(encoding='utf-8')
            existing_packages = {
                re.split(r'[<>=]', line, 1)[0].strip().lower()
                for line in original_content.splitlines()
                if line.strip() and not line.strip().startswith('#')
            }

            new_entries = [
                pkg for pkg in sorted(packages)
                if re.split(r'[<>=]', pkg, 1)[0].strip().lower() not in existing_packages
            ]

            if new_entries:
                with requirements_path.open('a', encoding='utf-8') as f:
                    if not original_content.endswith('\n'):
                        f.write('\n')
                    f.write('\n'.join(new_entries) + '\n')
                logger.info("Added %d dependencies to backend requirements: %s", len(new_entries), ', '.join(new_entries))
        except OSError as exc:
            logger.warning("Failed to update backend requirements: %s", exc)
    
    def _process_frontend(self, raw_content: str) -> Dict[str, Path]:
        """Process frontend code blocks - merges ALL JSX code into App.jsx.

        Even if the LLM generates multiple files (pages/*.jsx, components/*.jsx),
        we merge everything into a single App.jsx for the single-file architecture.
        """
        written = {}
        blocks = self._extract_code_blocks(raw_content)
        if not blocks and self._looks_like_jsx(raw_content):
            blocks = [{'language': 'jsx', 'filename': 'App.jsx', 'code': raw_content.strip()}]
        frontend_src = self.frontend_dir / 'src'

        # Collect all JS/JSX code blocks
        jsx_blocks = []
        for block in blocks:
            lang = (block['language'] or '').strip().lower()
            filename = (block['filename'] or '').strip()
            code = block['code']

            if not filename and lang.endswith(('.jsx', '.js', '.tsx', '.ts')):
                filename = lang
                lang = 'jsx'

            if not lang and filename.lower().endswith(('.jsx', '.js', '.tsx', '.ts')):
                lang = 'jsx'

            # Handle CSS
            if lang == 'css':
                target_filename = filename.lstrip('/') if filename else 'App.css'
                if not target_filename.endswith('.css'):
                    target_filename += '.css'
                target_path = frontend_src / target_filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                written[f'css_{target_filename}'] = target_path
                logger.info(f"✓ Wrote frontend/src/{target_filename}")
                continue

            # Handle package.json
            if lang == 'json' and filename and 'package' in filename.lower():
                self._merge_package_json(code)
                continue

            # Handle JS/JSX files
            if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                jsx_blocks.append({
                    'filename': filename or 'App.jsx',
                    'code': code
                })
            elif not lang and self._looks_like_jsx(code):
                jsx_blocks.append({
                    'filename': filename or 'App.jsx',
                    'code': code
                })

        if not jsx_blocks:
            error_msg = "No JSX code blocks found in frontend response"
            logger.warning(error_msg)
            raise RuntimeError(error_msg)

        # Check if we have a single App.jsx block
        app_blocks = [b for b in jsx_blocks
                      if b['filename'].lower().rstrip('.jsx').rstrip('.js').rstrip('.tsx')
                      in ('app', 'src/app', '')]

        if len(jsx_blocks) == 1:
            # Single file case - use as-is
            code = jsx_blocks[0]['code']
        elif app_blocks and len(app_blocks) == 1 and len(jsx_blocks) <= 2:
            # Main App.jsx with maybe one helper - use App.jsx
            code = app_blocks[0]['code']
        else:
            # Multiple files case - merge into single App.jsx
            logger.info(f"Merging {len(jsx_blocks)} JSX files into App.jsx")
            code = self._merge_jsx_files(jsx_blocks)

        # Fix API URLs
        code = self._fix_api_urls(code)

        # Ensure default export for App component
        if 'export default' not in code:
            if 'function App' in code:
                code += "\n\nexport default App;"

        # Write the merged App.jsx
        target_path = frontend_src / 'App.jsx'
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(code, encoding='utf-8')
        written['frontend_App'] = target_path
        logger.info(f"✓ Wrote frontend/src/App.jsx ({len(code)} chars)")

        return written

    def _looks_like_jsx(self, code: str) -> bool:
        """Heuristic check for JSX/React code presence."""
        if not code:
            return False
        signals = (
            r"\bimport\s+React\b",
            r"from\s+['\"]react['\"]",
            r"\bfunction\s+App\b",
            r"\bconst\s+App\b",
            r"\bexport\s+default\s+App\b",
            r"<div[^>]*>",
            r"return\s*\("
        )
        return any(re.search(pattern, code) for pattern in signals)

    def _looks_like_python(self, code: str) -> bool:
        """Heuristic check for Python code presence."""
        if not code:
            return False
        signals = (
            r"\bimport\s+\w+",
            r"\bfrom\s+\w+\s+import\b",
            r"\bdef\s+\w+\(.*\):",
            r"\bclass\s+\w+\b",
            r"app\s*=\s*Flask\(",
            r"@app\.route\(",
        )
        return any(re.search(pattern, code, re.MULTILINE) for pattern in signals)

    def _merge_jsx_files(self, blocks: List[Dict[str, str]]) -> str:
        """Merge multiple JSX code blocks into a single App.jsx file.

        Strategy:
        1. Collect all imports from all files
        2. Collect components (pages, etc.)
        3. Collect main App component
        4. Reassemble with proper export
        """
        all_imports = set()
        api_code = []
        auth_code = []
        component_code = []
        app_code = []

        import_pattern = re.compile(r"^import\s+.+$", re.MULTILINE)

        for block in blocks:
            code = block['code']
            filename = block['filename'].lower()

            # Extract imports - collect all import statements from each file
            # Skip relative imports that won't work in single-file architecture
            for match in import_pattern.finditer(code):
                import_line = match.group().strip()
                # Skip relative imports
                if not import_line.startswith("import ") or \
                   "'." not in import_line and '"./' not in import_line:
                    all_imports.add(import_line)

            # Remove imports from code for further processing
            code_without_imports = import_pattern.sub('', code).strip()

            # Also remove any export default at the end (we'll add one final export)
            code_without_imports = re.sub(
                r'\nexport\s+default\s+\w+;?\s*$', '', code_without_imports
            ).strip()

            # Categorize code blocks by filename patterns to organize the merged file
            if 'api' in filename or 'service' in filename:
                api_code.append(f"// From {block['filename']}\n{code_without_imports}")
            elif 'auth' in filename or 'context' in filename:
                auth_code.append(f"// From {block['filename']}\n{code_without_imports}")
            elif filename.rstrip('.jsx').rstrip('.js').rstrip('.tsx') in ('app', 'src/app', ''):
                app_code.append(code_without_imports)
            else:
                component_code.append(f"// From {block['filename']}\n{code_without_imports}")

        # Build merged file with proper organization
        parts = []

        # Standard imports first
        parts.append("// Merged from multiple generated files into single App.jsx")
        parts.append("")

        # Sort and add imports (React first, then others)
        def import_sort_key(imp):
            if "'react'" in imp or '"react"' in imp:
                return (0, imp)
            if "'react-" in imp or '"react-' in imp:
                return (1, imp)
            return (2, imp)

        sorted_imports = sorted(all_imports, key=import_sort_key)
        parts.extend(sorted_imports)
        parts.append("")

        # Add API code
        if api_code:
            parts.append("// " + "=" * 70)
            parts.append("// API CLIENT")
            parts.append("// " + "=" * 70)
            parts.extend(api_code)
            parts.append("")

        # Add auth code
        if auth_code:
            parts.append("// " + "=" * 70)
            parts.append("// AUTH CONTEXT")
            parts.append("// " + "=" * 70)
            parts.extend(auth_code)
            parts.append("")

        # Add component code
        if component_code:
            parts.append("// " + "=" * 70)
            parts.append("// COMPONENTS & PAGES")
            parts.append("// " + "=" * 70)
            parts.extend(component_code)
            parts.append("")

        # Add app code
        if app_code:
            parts.append("// " + "=" * 70)
            parts.append("// MAIN APP")
            parts.append("// " + "=" * 70)
            parts.extend(app_code)

        # Add final export
        parts.append("")
        parts.append("export default App;")

        return '\n'.join(parts)
    
    def _fix_api_urls(self, code: str) -> str:
        """Fix API URLs for Docker networking."""
        if 'localhost:5000' in code or 'localhost:5001' in code:
            code = re.sub(r'http://localhost:500[01]', '', code, flags=re.IGNORECASE)
        return code
    
    def _merge_requirements(self, requirements_content: str) -> None:
        """Merge additional requirements into backend/requirements.txt."""
        if not requirements_content.strip():
            return
        
        requirements_path = self.backend_dir / 'requirements.txt'
        if not requirements_path.exists():
            return
        
        try:
            existing = requirements_path.read_text(encoding='utf-8')
            existing_packages = {
                re.split(r'[<>=]', line, 1)[0].strip().lower()
                for line in existing.splitlines()
                if line.strip() and not line.strip().startswith('#')
            }
            
            new_lines = []
            for line in requirements_content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                pkg_name = re.split(r'[<>=]', line, 1)[0].strip().lower()
                if pkg_name and pkg_name not in existing_packages:
                    new_lines.append(line)
            
            if new_lines:
                with requirements_path.open('a', encoding='utf-8') as f:
                    if not existing.endswith('\n'):
                        f.write('\n')
                    f.write('\n'.join(new_lines) + '\n')
                logger.info(f"Merged {len(new_lines)} requirements")
        except Exception as e:
            logger.warning(f"Failed to merge requirements: {e}")
    
    def _merge_package_json(self, package_json_content: str) -> None:
        """Merge dependencies into frontend/package.json."""
        if not package_json_content.strip():
            return
        
        package_path = self.frontend_dir / 'package.json'
        if not package_path.exists():
            return
        
        try:
            incoming = json.loads(package_json_content)
        except json.JSONDecodeError:
            return
        
        try:
            existing = json.loads(package_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return
        
        # Merge dependencies
        for dep_key in ['dependencies', 'devDependencies']:
            if isinstance(incoming.get(dep_key), dict):
                existing.setdefault(dep_key, {})
                existing[dep_key].update(incoming.get(dep_key, {}))
        
        package_path.write_text(json.dumps(existing, indent=2) + '\n', encoding='utf-8')
        logger.info("Merged package.json dependencies")
