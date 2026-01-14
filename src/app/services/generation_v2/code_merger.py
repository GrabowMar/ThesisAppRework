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
    - frontend_user → frontend/src/pages/UserPage.jsx, frontend/src/services/api.js
    - frontend_admin → frontend/src/pages/AdminPage.jsx
    
    The scaffolding already includes App.jsx with routing - we write to
    pages/UserPage.jsx and pages/AdminPage.jsx which are imported by App.jsx.
    
    Handles:
    - Annotated code blocks (```jsx:pages/UserPage.jsx)
    - Model class merging (deduplicate User model)
    - Import consolidation
    """
    
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir
        self.backend_dir = app_dir / 'backend'
        self.frontend_dir = app_dir / 'frontend'
    
    def _extract_all_code_blocks(self, content: str) -> List[Dict[str, str]]:
        """Extract all code blocks from content, including filename annotations.
        
        Supports formats:
        - ```python
        - ```python:filename.py
        - ```jsx:components/MyComponent.jsx
        - ```css:App.css
        
        Returns list of dicts with 'language', 'filename', and 'code' keys.
        """
        blocks = []
        # Pattern matches ```lang or ```lang:filename
        pattern = re.compile(
            r"```(?P<lang>[a-zA-Z0-9_+-]+)?(?::(?P<filename>[^\n\r`]+))?\s*[\r\n]+(.*?)```",
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
            all_blocks = self._extract_all_code_blocks(backend_user)
            
            # Extract and write models
            models_code = self._find_backend_file(all_blocks, backend_user, 'models.py')
            if models_code:
                path = self._write_backend_file('models.py', models_code)
                written_files['models'] = path
            
            # Extract and write user routes
            routes_code = self._find_backend_file(all_blocks, backend_user, 'user.py', 'routes')
            if routes_code:
                path = self._write_backend_file('routes/user.py', routes_code)
                written_files['user_routes'] = path
            
            # Extract services if present
            services_code = self._find_backend_file(all_blocks, backend_user, 'services.py')
            if services_code:
                path = self._write_backend_file('services.py', services_code)
                written_files['services'] = path
        
        # Backend admin: routes/admin.py
        if 'backend_admin' in code:
            backend_admin = code['backend_admin']
            all_blocks = self._extract_all_code_blocks(backend_admin)
            routes_code = self._find_backend_file(all_blocks, backend_admin, 'admin.py', 'routes')
            if routes_code:
                path = self._write_backend_file('routes/admin.py', routes_code)
                written_files['admin_routes'] = path
        
        # Frontend user: pages/UserPage.jsx + services/api.js + hooks + components
        if 'frontend_user' in code:
            frontend_user = code['frontend_user']
            all_blocks = self._extract_all_code_blocks(frontend_user)
            
            user_files = self._merge_frontend_user(all_blocks, frontend_user)
            written_files.update(user_files)
        
        # Frontend admin: pages/AdminPage.jsx
        if 'frontend_admin' in code:
            frontend_admin = code['frontend_admin']
            all_blocks = self._extract_all_code_blocks(frontend_admin)
            
            admin_files = self._merge_frontend_admin(all_blocks, frontend_admin)
            written_files.update(admin_files)
        
        logger.info(f"Merged {len(written_files)} files")
        return written_files
    
    def _merge_frontend_user(self, all_blocks: List[Dict], raw_content: str) -> Dict[str, Path]:
        """Handle frontend merge for 'user' query.
        
        Writes to pages/UserPage.jsx, services/api.js, hooks/, components/.
        Does NOT overwrite App.jsx - the scaffolding already has routing.
        """
        written = {}
        frontend_src_dir = self.frontend_dir / 'src'
        
        # Find main JSX code (the user page content)
        # Priority: explicit pages/UserPage.jsx > UserPage.jsx > unnamed block
        main_code = None
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '').lower()
            if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                if 'userpage' in filename:
                    main_code = block['code']
                    logger.info("Found explicit UserPage.jsx block")
                    break
        
        # If no explicit UserPage, look for unnamed block
        if not main_code:
            for block in all_blocks:
                lang = block.get('language', '').lower()
                filename = block.get('filename', '').lower()
                if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                    if not filename:
                        main_code = block['code']
                        logger.info("Using unnamed JSX block as UserPage content")
                        break
                    elif filename in {'app.jsx', 'src/app.jsx'}:
                        # Check if it's page content (not router code)
                        if 'Routes' not in block['code'] and 'BrowserRouter' not in block['code']:
                            main_code = block['code']
                            logger.info("Block named app.jsx appears to be page content")
                            break
        
        if main_code:
            # Fix API URLs for Docker networking
            main_code = self._fix_api_urls(main_code)
            
            # Ensure export default exists
            if 'export default' not in main_code:
                func_match = re.search(r'function\s+(\w+)', main_code)
                export_name = func_match.group(1) if func_match else 'UserPage'
                logger.info(f"Adding missing 'export default {export_name};'")
                main_code += f"\n\nexport default {export_name};"
            
            # Write to pages/UserPage.jsx
            user_page_path = frontend_src_dir / 'pages' / 'UserPage.jsx'
            user_page_path.parent.mkdir(parents=True, exist_ok=True)
            user_page_path.write_text(main_code, encoding='utf-8')
            logger.info(f"✓ Wrote {len(main_code)} chars to pages/UserPage.jsx")
            written['user_page'] = user_page_path
        
        # Handle additional frontend files
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '')
            code = block.get('code', '')
            
            if not filename or not code:
                continue
            
            filename_lower = filename.lower()
            
            # Skip if already handled as UserPage
            if 'userpage' in filename_lower:
                continue
            if filename_lower in {'app.jsx', 'src/app.jsx'}:
                # Only write if it's router code
                if 'Routes' in code or 'BrowserRouter' in code:
                    app_jsx_path = frontend_src_dir / 'App.jsx'
                    app_jsx_path.write_text(code, encoding='utf-8')
                    logger.info("✓ Wrote router code to App.jsx")
                    written['app_jsx'] = app_jsx_path
                continue
            
            # Handle CSS files
            if lang == 'css' or filename.endswith('.css'):
                target_filename = filename if filename.endswith('.css') else 'App.css'
                target_path = frontend_src_dir / target_filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ Wrote CSS: {target_filename}")
                written[f'css_{target_filename}'] = target_path
            
            # Handle JS/JSX files (api.js, hooks, components)
            elif lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                code = self._fix_api_urls(code)
                
                # Ensure api.js has default export (required by scaffold's auth.js)
                if filename_lower in {'api.js', 'services/api.js'}:
                    if 'export default' not in code:
                        # Add default export for api instance
                        code = code.rstrip() + '\n\nexport default api;'
                        logger.info("Added 'export default api;' to api.js for scaffold compatibility")
                
                target_path = frontend_src_dir / filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ Wrote component: {filename}")
                written[f'component_{filename}'] = target_path
        
        return written
    
    def _merge_frontend_admin(self, all_blocks: List[Dict], raw_content: str) -> Dict[str, Path]:
        """Handle frontend merge for 'admin' query.
        
        Writes to pages/AdminPage.jsx and related admin files.
        """
        written = {}
        frontend_src_dir = self.frontend_dir / 'src'
        
        # Find AdminPage content
        main_code = None
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '').lower()
            if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                if 'adminpage' in filename:
                    main_code = block['code']
                    logger.info("Found explicit AdminPage.jsx block")
                    break
        
        # Try unnamed blocks if no explicit AdminPage
        if not main_code:
            for block in all_blocks:
                lang = block.get('language', '').lower()
                filename = block.get('filename', '')
                if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                    if not filename:
                        main_code = block['code']
                        logger.info("Using unnamed JSX block as AdminPage content")
                        break
        
        if main_code:
            main_code = self._fix_api_urls(main_code)
            
            if 'export default' not in main_code:
                func_match = re.search(r'function\s+(\w+)', main_code)
                export_name = func_match.group(1) if func_match else 'AdminPage'
                main_code += f"\n\nexport default {export_name};"
            
            admin_page_path = frontend_src_dir / 'pages' / 'AdminPage.jsx'
            admin_page_path.parent.mkdir(parents=True, exist_ok=True)
            admin_page_path.write_text(main_code, encoding='utf-8')
            logger.info(f"✓ Wrote {len(main_code)} chars to pages/AdminPage.jsx")
            written['admin_page'] = admin_page_path
        
        # Handle additional admin files
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '')
            code = block.get('code', '')
            
            if not filename or not code:
                continue
            
            filename_lower = filename.lower()
            
            if 'adminpage' in filename_lower:
                continue
            
            # Only write admin-related files
            if 'admin' in filename_lower or filename_lower.startswith('components/'):
                if lang == 'css' or filename.endswith('.css'):
                    target_path = frontend_src_dir / filename
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(code, encoding='utf-8')
                    logger.info(f"✓ Wrote admin CSS: {filename}")
                    written[f'admin_css_{filename}'] = target_path
                elif lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                    code = self._fix_api_urls(code)
                    
                    # Ensure api.js has default export (required by scaffold's auth.js)
                    if filename_lower in {'api.js', 'services/api.js'}:
                        if 'export default' not in code:
                            code = code.rstrip() + '\n\nexport default api;'
                            logger.info("Added 'export default api;' to api.js for scaffold compatibility")
                    
                    target_path = frontend_src_dir / filename
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(code, encoding='utf-8')
                    logger.info(f"✓ Wrote admin component: {filename}")
                    written[f'admin_component_{filename}'] = target_path
        
        return written
    
    def _fix_api_urls(self, code: str) -> str:
        """Fix API URLs for Docker networking (localhost → relative path)."""
        if 'localhost:5000' in code or 'localhost:5001' in code:
            logger.info("Fixing API_URL: replacing localhost with relative path")
            code = re.sub(r'http://localhost:500[01]', '', code, flags=re.IGNORECASE)
        return code
    
    def _find_backend_file(self, all_blocks: List[Dict], raw_content: str, 
                           filename: str, subdir: str = None) -> Optional[str]:
        """Find a specific backend file from code blocks.
        
        Priority:
        1. Annotated block matching filename
        2. Header-based extraction
        3. Single Python block (if only one)
        """
        # Try annotated blocks first
        for block in all_blocks:
            lang = block.get('language', '').lower()
            block_filename = block.get('filename', '').lower()
            
            if lang == 'python':
                if subdir:
                    if f'{subdir}/{filename}'.lower() in block_filename:
                        return block['code']
                else:
                    if filename.lower() in block_filename:
                        return block['code']
        
        # Fall back to header-based extraction
        return self._extract_python_file(raw_content, filename, subdir)
    
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
            backend_code = code['backend']
            all_blocks = self._extract_all_code_blocks(backend_code)
            
            # Try to find app.py block, or use first Python block
            app_code = None
            for block in all_blocks:
                if block['language'] == 'python':
                    app_code = block['code']
                    break
            
            if not app_code:
                # Use raw content if no blocks
                app_code = backend_code
            
            path = self._write_backend_file('app.py', app_code)
            written_files['backend'] = path
        
        if 'frontend' in code and code['frontend'].strip():
            frontend = code['frontend']
            all_blocks = self._extract_all_code_blocks(frontend)
            
            # Try to extract JSX from code fences first
            jsx_code = None
            for block in all_blocks:
                if block['language'] in {'jsx', 'javascript', 'js'}:
                    jsx_code = block['code']
                    break
            
            # If no fences found, check if it's raw JSX code
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
                jsx_code = self._fix_api_urls(jsx_code)
                path = self._write_frontend_file('src/App.jsx', jsx_code)
                written_files['app_jsx'] = path
            
            # Extract CSS
            for block in all_blocks:
                if block['language'] == 'css':
                    path = self._write_frontend_file('src/App.css', block['code'])
                    written_files['app_css'] = path
                    break
        
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
