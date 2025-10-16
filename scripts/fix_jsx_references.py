#!/usr/bin/env python3
"""
Fix incorrect .jsx references in index.html files where the actual files are .js
This is a common generation issue where the AI creates .js files but references them as .jsx
"""

import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# pylint: disable=wrong-import-position
from app.paths import GENERATED_APPS_DIR


def fix_jsx_references():
    """Fix .jsx references in index.html to match actual .js files."""
    
    fixed_count = 0
    checked_count = 0
    
    # Find all frontend directories
    for model_dir in GENERATED_APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.glob("app*"):
            if not app_dir.is_dir():
                continue
            
            frontend_dir = app_dir / "frontend"
            if not frontend_dir.exists():
                continue
            
            index_html = frontend_dir / "index.html"
            if not index_html.exists():
                continue
            
            checked_count += 1
            
            # Read index.html
            content = index_html.read_text(encoding='utf-8')
            original_content = content
            
            # Check for .jsx references
            if '/src/main.jsx' in content:
                # Check if main.js exists instead
                main_js = frontend_dir / "src" / "main.js"
                main_jsx = frontend_dir / "src" / "main.jsx"
                
                if main_js.exists() and not main_jsx.exists():
                    # Fix the reference
                    content = content.replace('/src/main.jsx', '/src/main.js')
                    index_html.write_text(content, encoding='utf-8')
                    fixed_count += 1
                    print(f"✓ Fixed {index_html.relative_to(GENERATED_APPS_DIR)}")
    
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Checked: {checked_count} apps")
    print(f"  Fixed: {fixed_count} apps")
    print(f"{'='*60}")
    
    return True


if __name__ == "__main__":
    print("Fixing .jsx references in index.html files...")
    print(f"Apps directory: {GENERATED_APPS_DIR}\n")
    
    success = fix_jsx_references()
    sys.exit(0 if success else 1)
