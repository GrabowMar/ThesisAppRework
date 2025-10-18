"""Fix Missing Frontend Entry Points
===================================

Many generated frontends are missing main.jsx, causing blank pages.
This script:
1. Detects missing main.jsx files
2. Generates proper React entry points
3. Fixes index.html to point to main.jsx
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


MAIN_JSX_TEMPLATE = """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './App.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""


def fix_frontend_entry_point(app_dir: Path) -> tuple[bool, str]:
    """Fix missing main.jsx and update index.html."""
    
    frontend_dir = app_dir / 'frontend'
    src_dir = frontend_dir / 'src'
    
    if not src_dir.exists():
        return False, "Frontend src directory not found"
    
    main_jsx = src_dir / 'main.jsx'
    index_html = frontend_dir / 'index.html'
    app_jsx = src_dir / 'App.jsx'
    
    # Check if App.jsx exists
    if not app_jsx.exists():
        return False, "App.jsx not found"
    
    changes = []
    
    # Create main.jsx if missing
    if not main_jsx.exists():
        main_jsx.write_text(MAIN_JSX_TEMPLATE, encoding='utf-8')
        changes.append("Created main.jsx")
        logger.info(f"Created {main_jsx}")
    
    # Fix index.html to point to main.jsx
    if index_html.exists():
        content = index_html.read_text(encoding='utf-8')
        
        # Check if it's pointing to the wrong file
        if '/src/App.jsx' in content:
            content = content.replace('/src/App.jsx', '/src/main.jsx')
            index_html.write_text(content, encoding='utf-8')
            changes.append("Fixed index.html to use main.jsx")
            logger.info(f"Updated {index_html}")
    
    if changes:
        return True, "; ".join(changes)
    else:
        return True, "No changes needed"


def scan_and_fix_all_frontends(base_dir: Path) -> dict[str, tuple[bool, str]]:
    """Scan all generated apps and fix frontend entry points."""
    
    results = {}
    
    for model_dir in base_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            app_path = f"{model_dir.name}/{app_dir.name}"
            logger.info(f"Checking {app_path}...")
            
            success, message = fix_frontend_entry_point(app_dir)
            results[app_path] = (success, message)
    
    return results


def main():
    """Main entry point."""
    import sys
    from pathlib import Path
    
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    
    from app.paths import GENERATED_APPS_DIR
    
    logging.basicConfig(level=logging.INFO)
    
    print("Scanning generated apps for missing frontend entry points...")
    print("=" * 60)
    
    results = scan_and_fix_all_frontends(GENERATED_APPS_DIR)
    
    print("\nResults:")
    print("=" * 60)
    
    for app_path, (success, message) in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {app_path}")
        if message != "No changes needed":
            print(f"  {message}")
    
    print(f"\nProcessed {len(results)} apps")


if __name__ == "__main__":
    main()
