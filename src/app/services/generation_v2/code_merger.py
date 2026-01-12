"""Code Merger
=============

Merges generated code into the scaffolded app structure.
Handles AST-based model merging and file organization.
"""

import ast
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class CodeMerger:
    """Merges generated code into app directory.
    
    Guarded mode file mapping:
    - backend_user → backend/models.py, backend/routes/user.py, backend/services.py
    - backend_admin → backend/routes/admin.py
    - frontend_user → frontend/src/App.jsx, frontend/src/App.css
    - frontend_admin → frontend/src/components/AdminDashboard.jsx
    
    Handles:
    - Model class merging (deduplicate User model)
    - Import consolidation
    - CSS file writing
    """
    
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.backend_dir = app_dir / 'backend'
        self.frontend_dir = app_dir / 'frontend'
    
    def merge_guarded(self, code: Dict[str, str]) -> Dict[str, Path]:
        """Merge guarded mode code (4 queries).
        
        Args:
            code: Dict with backend_user, backend_admin, frontend_user, frontend_admin
            
        Returns:
            Dict mapping file type to written path
        """
        written_files = {}
        
        # Backend user: models.py + routes/user.py
        if 'backend_user' in code:
            backend_user = code['backend_user']
            
            # Extract and write models
            models_code = self._extract_python_file(backend_user, 'models.py')
            if models_code:
                path = self._write_backend_file('models.py', models_code)
                written_files['models'] = path
            
            # Extract and write user routes
            routes_code = self._extract_python_file(backend_user, 'user.py', 'routes')
            if routes_code:
                path = self._write_backend_file('routes/user.py', routes_code)
                written_files['user_routes'] = path
            
            # Extract services if present
            services_code = self._extract_python_file(backend_user, 'services.py')
            if services_code:
                path = self._write_backend_file('services.py', services_code)
                written_files['services'] = path
        
        # Backend admin: routes/admin.py
        if 'backend_admin' in code:
            backend_admin = code['backend_admin']
            routes_code = self._extract_python_file(backend_admin, 'admin.py', 'routes')
            if routes_code:
                path = self._write_backend_file('routes/admin.py', routes_code)
                written_files['admin_routes'] = path
        
        # Frontend user: App.jsx + App.css
        if 'frontend_user' in code:
            frontend_user = code['frontend_user']
            
            jsx_code = self._extract_jsx(frontend_user)
            if jsx_code:
                path = self._write_frontend_file('src/App.jsx', jsx_code)
                written_files['app_jsx'] = path
            
            css_code = self._extract_css(frontend_user)
            if css_code:
                path = self._write_frontend_file('src/App.css', css_code)
                written_files['app_css'] = path
        
        # Frontend admin: AdminDashboard.jsx
        if 'frontend_admin' in code:
            frontend_admin = code['frontend_admin']
            jsx_code = self._extract_jsx(frontend_admin)
            if jsx_code:
                path = self._write_frontend_file('src/components/AdminDashboard.jsx', jsx_code)
                written_files['admin_jsx'] = path
        
        logger.info(f"Merged {len(written_files)} files")
        return written_files
    
    def merge_unguarded(self, code: Dict[str, str]) -> Dict[str, Path]:
        """Merge unguarded mode code (2 queries).
        
        Args:
            code: Dict with backend, frontend keys
            
        Returns:
            Dict mapping file type to written path
        """
        written_files = {}
        
        if 'backend' in code and code['backend'].strip():
            # Write entire backend as app.py
            path = self._write_backend_file('app.py', code['backend'])
            written_files['backend'] = path
        
        if 'frontend' in code and code['frontend'].strip():
            frontend = code['frontend']
            
            # Try to extract JSX from code fences first
            jsx_code = self._extract_jsx(frontend)
            
            # If no fences found, check if it's raw JSX code (starts with import/function/const)
            if not jsx_code:
                first_line = frontend.strip().split('\n')[0].strip() if frontend.strip() else ''
                looks_like_jsx = (
                    first_line.startswith('import ') or
                    first_line.startswith('function ') or
                    first_line.startswith('const ') or
                    first_line.startswith('export ')
                )
                if looks_like_jsx:
                    jsx_code = frontend
            
            if jsx_code:
                path = self._write_frontend_file('src/App.jsx', jsx_code)
                written_files['app_jsx'] = path
            
            # Try to extract CSS
            css_code = self._extract_css(frontend)
            if css_code:
                path = self._write_frontend_file('src/App.css', css_code)
                written_files['app_css'] = path
        
        logger.info(f"Merged {len(written_files)} files")
        return written_files
    
    def _extract_python_file(self, content: str, filename: str, subdir: str = None) -> Optional[str]:
        """Extract Python code for a specific file from generated content.
        
        Looks for:
        - ```python:filename.py blocks
        - # filename.py headers
        """
        # Try annotated code block first
        pattern = rf'```python:{re.escape(filename)}\s*\n(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try header-based extraction
        if subdir:
            header_pattern = rf'#\s*{re.escape(subdir)}/{re.escape(filename)}\s*\n(.*?)(?=\n#\s*\w+\.py|\Z)'
        else:
            header_pattern = rf'#\s*{re.escape(filename)}\s*\n(.*?)(?=\n#\s*\w+\.py|\Z)'
        
        match = re.search(header_pattern, content, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Remove code fences if wrapped
            code = re.sub(r'^```python\s*\n?', '', code)
            code = re.sub(r'\n?```\s*$', '', code)
            return code.strip()
        
        # If single file expected, extract first Python block
        blocks = re.findall(r'```python\s*\n(.*?)```', content, re.DOTALL)
        if len(blocks) == 1:
            return blocks[0].strip()
        
        return None
    
    def _extract_jsx(self, content: str) -> Optional[str]:
        """Extract JSX/JavaScript code from content."""
        # Try jsx/javascript code blocks
        patterns = [
            r'```jsx\s*\n(.*?)```',
            r'```javascript\s*\n(.*?)```',
            r'```js\s*\n(.*?)```',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Try annotated blocks
        for ext in ['jsx', 'js']:
            pattern = rf'```{ext}:[^\n]+\.{ext}\s*\n(.*?)```'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_css(self, content: str) -> Optional[str]:
        """Extract CSS code from content."""
        pattern = r'```css\s*\n(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _write_backend_file(self, rel_path: str, content: str) -> Path:
        """Write a file to the backend directory."""
        full_path = self.backend_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean up content
        content = self._clean_python(content)
        
        full_path.write_text(content, encoding='utf-8')
        logger.debug(f"Wrote backend/{rel_path} ({len(content)} chars)")
        return full_path
    
    def _write_frontend_file(self, rel_path: str, content: str) -> Path:
        """Write a file to the frontend directory."""
        full_path = self.frontend_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_text(content, encoding='utf-8')
        logger.debug(f"Wrote frontend/{rel_path} ({len(content)} chars)")
        return full_path
    
    def _clean_python(self, code: str) -> str:
        """Clean Python code - remove duplicate imports, fix common issues."""
        if not code:
            return code
        
        lines = code.split('\n')
        seen_imports = set()
        cleaned = []
        
        for line in lines:
            # Deduplicate imports
            if line.strip().startswith(('import ', 'from ')):
                if line.strip() in seen_imports:
                    continue
                seen_imports.add(line.strip())
            
            cleaned.append(line)
        
        return '\n'.join(cleaned)
    
    def merge_models(self, existing_path: Path, new_code: str) -> str:
        """Merge model classes, preserving existing User model.
        
        Args:
            existing_path: Path to existing models.py (from scaffolding)
            new_code: New model code to merge
            
        Returns:
            Merged model code
        """
        if not existing_path.exists():
            return new_code
        
        try:
            existing = existing_path.read_text(encoding='utf-8')
            
            # Parse both
            existing_tree = ast.parse(existing)
            new_tree = ast.parse(new_code)
            
            # Get class names from each
            existing_classes = {
                node.name for node in ast.walk(existing_tree)
                if isinstance(node, ast.ClassDef)
            }
            new_classes = {
                node.name for node in ast.walk(new_tree)
                if isinstance(node, ast.ClassDef)
            }
            
            # If new code redefines User, use existing User
            if 'User' in existing_classes and 'User' in new_classes:
                logger.info("Preserving existing User model from scaffolding")
                # Filter out User class from new code
                new_code = self._remove_class(new_code, 'User')
            
            # Combine: existing imports + existing classes + new classes
            return self._combine_python_modules(existing, new_code)
            
        except SyntaxError as e:
            logger.warning(f"Could not parse for merging: {e}")
            return new_code
    
    def _remove_class(self, code: str, class_name: str) -> str:
        """Remove a class definition from code."""
        # Simple regex-based removal
        pattern = rf'^class {class_name}\([^)]*\):.*?(?=\nclass |\n[^\s]|\Z)'
        return re.sub(pattern, '', code, flags=re.MULTILINE | re.DOTALL).strip()
    
    def _combine_python_modules(self, existing: str, new: str) -> str:
        """Combine two Python modules, deduplicating imports."""
        # Extract imports from both
        existing_imports = set(re.findall(r'^(?:import|from)\s+.+$', existing, re.MULTILINE))
        new_imports = set(re.findall(r'^(?:import|from)\s+.+$', new, re.MULTILINE))
        
        all_imports = sorted(existing_imports | new_imports)
        
        # Remove imports from both modules
        existing_body = re.sub(r'^(?:import|from)\s+.+\n?', '', existing, flags=re.MULTILINE)
        new_body = re.sub(r'^(?:import|from)\s+.+\n?', '', new, flags=re.MULTILINE)
        
        # Combine
        return '\n'.join(all_imports) + '\n\n' + existing_body.strip() + '\n\n' + new_body.strip()
