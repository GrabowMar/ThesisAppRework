#!/usr/bin/env python3
"""
Automated fix script for common AI-generated app issues.

Fixes:
1. Missing main.jsx entry points
2. Unreplaced {{app_num}} placeholders
3. Flask 2.x before_first_request (deprecated in Flask 3.0)
4. Other common generation issues

Usage:
    python scripts/fix_generated_apps.py [model_folder]
    python scripts/fix_generated_apps.py                    # Fix all models
    python scripts/fix_generated_apps.py openai_gpt-4      # Fix specific model
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Set

# Script configuration
GENERATED_APPS_DIR = Path(__file__).parent.parent / "generated" / "apps"
MAIN_JSX_TEMPLATE = '''import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './App.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
'''

FLASK_DB_INIT_OLD = r'@app\.before_first_request\s*\ndef\s+\w+\(\):\s*"""[^"]*"""\s*try:\s*db\.create_all\(\)\s*logger\.info\([^)]+\)\s*except[^:]+:\s*logger\.error\([^)]+\)'

FLASK_DB_INIT_NEW = '''# Flask 3.0+ compatible: Initialize database in application context
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")'''


class AppFixer:
    """Fixes common issues in AI-generated applications."""
    
    def __init__(self, model_folder: Path):
        self.model_folder = model_folder
        self.fixes_applied: Dict[str, List[str]] = {}
        
    def fix_all_apps(self) -> Dict[str, List[str]]:
        """Fix all apps in the model folder."""
        app_dirs = [d for d in self.model_folder.iterdir() if d.is_dir() and d.name.startswith('app')]
        
        for app_dir in sorted(app_dirs):
            app_name = app_dir.name
            self.fixes_applied[app_name] = []
            
            print(f"\n🔍 Checking {self.model_folder.name}/{app_name}...")
            
            # Fix 1: Missing main.jsx
            if self.fix_missing_main_jsx(app_dir):
                self.fixes_applied[app_name].append("Created main.jsx entry point")
                
            # Fix 2: Docker compose placeholders
            if self.fix_docker_compose_placeholders(app_dir):
                self.fixes_applied[app_name].append("Fixed docker-compose.yml placeholders")
                
            # Fix 3: Flask before_first_request
            if self.fix_flask_before_first_request(app_dir):
                self.fixes_applied[app_name].append("Fixed Flask 3.0 compatibility")
                
            if self.fixes_applied[app_name]:
                print(f"  ✅ Applied {len(self.fixes_applied[app_name])} fix(es)")
            else:
                print(f"  ✓ No fixes needed")
                
        return self.fixes_applied
    
    def fix_missing_main_jsx(self, app_dir: Path) -> bool:
        """Create main.jsx if it's missing but referenced in index.html."""
        frontend_src = app_dir / "frontend" / "src"
        main_jsx = frontend_src / "main.jsx"
        index_html = app_dir / "frontend" / "index.html"
        
        # Check if main.jsx is needed
        if not index_html.exists():
            return False
            
        with open(index_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        if '/src/main.jsx' not in html_content and '/src/index.jsx' not in html_content:
            return False
            
        if main_jsx.exists():
            return False
            
        # Create main.jsx
        frontend_src.mkdir(parents=True, exist_ok=True)
        with open(main_jsx, 'w', encoding='utf-8') as f:
            f.write(MAIN_JSX_TEMPLATE)
            
        print(f"    ✓ Created {main_jsx.relative_to(app_dir)}")
        return True
    
    def fix_docker_compose_placeholders(self, app_dir: Path) -> bool:
        """Replace {{app_num}} placeholders in docker-compose.yml."""
        compose_file = app_dir / "docker-compose.yml"
        
        if not compose_file.exists():
            return False
            
        with open(compose_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if '{{app_num}}' not in content:
            return False
            
        # Extract app number from directory name (e.g., app1 -> 1)
        app_num_match = re.search(r'app(\d+)', app_dir.name)
        if not app_num_match:
            print(f"    ⚠ Cannot extract app number from {app_dir.name}")
            return False
            
        app_num = app_num_match.group(1)
        
        # Replace placeholders
        new_content = content.replace('{{app_num}}', app_num)
        
        with open(compose_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"    ✓ Fixed container names (app{{{{app_num}}}} -> app{app_num})")
        return True
    
    def fix_flask_before_first_request(self, app_dir: Path) -> bool:
        """Replace Flask 2.x before_first_request with Flask 3.0 compatible code."""
        app_py = app_dir / "backend" / "app.py"
        
        if not app_py.exists():
            return False
            
        with open(app_py, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if '@app.before_first_request' not in content:
            return False
            
        # Find and replace the pattern
        pattern = r'@app\.before_first_request\s*\ndef\s+\w+\(\):[^\n]*\n\s*"""[^"]*"""\s*\n\s*try:\s*\n\s*db\.create_all\(\)\s*\n\s*logger\.info\([^)]+\)\s*\n\s*except[^:]+:\s*\n\s*logger\.error\([^)]+\)'
        
        if not re.search(pattern, content, re.MULTILINE | re.DOTALL):
            # Try simpler pattern
            lines = content.split('\n')
            fixed_lines = []
            in_before_first_request = False
            indent_level = 0
            
            for i, line in enumerate(lines):
                if '@app.before_first_request' in line:
                    in_before_first_request = True
                    indent_level = len(line) - len(line.lstrip())
                    # Replace decorator with new pattern
                    fixed_lines.append(' ' * indent_level + '# Flask 3.0+ compatible: Initialize database in application context')
                    fixed_lines.append(' ' * indent_level + 'with app.app_context():')
                    continue
                    
                if in_before_first_request:
                    stripped = line.lstrip()
                    if stripped.startswith('def '):
                        # Skip function definition
                        continue
                    elif stripped.startswith('"""'):
                        # Skip docstring
                        continue
                    elif stripped.startswith('try:'):
                        # Indent content under with block
                        fixed_lines.append(' ' * (indent_level + 4) + 'try:')
                    elif stripped.startswith('db.create_all'):
                        fixed_lines.append(' ' * (indent_level + 8) + 'db.create_all()')
                    elif stripped.startswith('logger.info'):
                        fixed_lines.append(' ' * (indent_level + 8) + 'logger.info("Database tables created successfully.")')
                    elif stripped.startswith('except'):
                        fixed_lines.append(' ' * (indent_level + 4) + 'except Exception as e:')
                    elif stripped.startswith('logger.error'):
                        fixed_lines.append(' ' * (indent_level + 8) + 'logger.error(f"Error creating database tables: {e}")')
                        in_before_first_request = False
                    continue
                    
                fixed_lines.append(line)
                
            content = '\n'.join(fixed_lines)
        
        with open(app_py, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"    ✓ Fixed Flask 3.0 @app.before_first_request deprecation")
        return True


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        model_name = sys.argv[1]
        model_folder = GENERATED_APPS_DIR / model_name
        
        if not model_folder.exists():
            print(f"❌ Model folder not found: {model_folder}")
            sys.exit(1)
            
        model_folders = [model_folder]
    else:
        # Fix all model folders
        model_folders = [d for d in GENERATED_APPS_DIR.iterdir() if d.is_dir()]
        
    print(f"🔧 Fixing generated apps in {len(model_folders)} model folder(s)...\n")
    
    total_fixes = {}
    for model_folder in sorted(model_folders):
        print(f"\n{'='*60}")
        print(f"Model: {model_folder.name}")
        print(f"{'='*60}")
        
        fixer = AppFixer(model_folder)
        fixes = fixer.fix_all_apps()
        
        # Collect stats
        for app_name, app_fixes in fixes.items():
            if app_fixes:
                total_fixes[f"{model_folder.name}/{app_name}"] = app_fixes
                
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    
    if total_fixes:
        print(f"\n✅ Applied fixes to {len(total_fixes)} app(s):\n")
        for app_path, fixes_list in total_fixes.items():
            print(f"  {app_path}:")
            for fix in fixes_list:
                print(f"    • {fix}")
    else:
        print("\n✓ No fixes needed - all apps are already correct!")
        
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
