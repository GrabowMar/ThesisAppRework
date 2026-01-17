"""Code Merger
=============

Merges generated code into the scaffolded app structure.
Simple file writing based on annotated code blocks.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

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
            backend_files = self._process_backend(code['backend'])
            written_files.update(backend_files)
        
        # Process frontend
        if 'frontend' in code and code['frontend'].strip():
            frontend_files = self._process_frontend(code['frontend'])
            written_files.update(frontend_files)
        
        logger.info(f"Merged {len(written_files)} files")
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
    
    def _process_backend(self, raw_content: str) -> Dict[str, Path]:
        """Process backend code blocks - expects single app.py file."""
        written = {}
        blocks = self._extract_code_blocks(raw_content)
        
        for block in blocks:
            lang = block['language']
            filename = block['filename']
            code = block['code']
            
            # Handle requirements block
            if lang == 'requirements' or (filename and 'requirements' in filename.lower()):
                self._merge_requirements(code)
                continue
            
            if lang != 'python':
                continue
            
            # Default to app.py if no filename or just "app"
            if not filename or filename.lower() in ('app', 'app.py', 'main', 'main.py'):
                filename = 'app.py'
            
            # Normalize filename
            filename = filename.lstrip('/')
            if not filename.endswith('.py'):
                filename += '.py'
            
            # Write the file
            target_path = self.backend_dir / filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(code, encoding='utf-8')
            
            key = filename.replace('/', '_').replace('.py', '')
            written[f'backend_{key}'] = target_path
            logger.info(f"✓ Wrote backend/{filename}")
        
        return written
    
    def _process_frontend(self, raw_content: str) -> Dict[str, Path]:
        """Process frontend code blocks - expects single App.jsx file."""
        written = {}
        blocks = self._extract_code_blocks(raw_content)
        frontend_src = self.frontend_dir / 'src'
        
        for block in blocks:
            lang = block['language']
            filename = block['filename']
            code = block['code']
            
            # Handle CSS
            if lang == 'css':
                target_filename = filename if filename else 'App.css'
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
            if lang not in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                continue
            
            # Default to App.jsx for main component
            if not filename or filename.lower() in ('app', 'app.jsx', 'app.js'):
                filename = 'App.jsx'
            
            # Normalize filename
            filename = filename.lstrip('/')
            
            # Fix API URLs
            code = self._fix_api_urls(code)
            
            # Ensure default export for App component
            if 'App' in filename and 'export default' not in code:
                func_match = re.search(r'function\s+(App)\b', code)
                if func_match:
                    code += f"\n\nexport default App;"
            
            # Write the file
            target_path = frontend_src / filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(code, encoding='utf-8')
            
            key = filename.replace('/', '_').replace('.jsx', '').replace('.js', '')
            written[f'frontend_{key}'] = target_path
            logger.info(f"✓ Wrote frontend/src/{filename}")
        
        return written
    
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
