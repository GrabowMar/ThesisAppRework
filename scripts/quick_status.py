"""Quick Status Check
===================

Check what's been generated so far.
"""

from pathlib import Path

apps_dir = Path("generated/apps/openai_gpt-4o-mini")

if not apps_dir.exists():
    print("No apps generated yet")
    exit()

for app_dir in sorted(apps_dir.iterdir()):
    if not app_dir.is_dir():
        continue
    
    print(f"\n{'='*60}")
    print(f"{app_dir.name}")
    print(f"{'='*60}")
    
    # Check backend
    backend_file = app_dir / 'backend' / 'app.py'
    if backend_file.exists():
        lines = len(backend_file.read_text(encoding='utf-8').split('\n'))
        print(f"✓ backend/app.py: {lines} lines")
    else:
        print(f"❌ backend/app.py: NOT FOUND")
    
    # Check frontend
    jsx_file = app_dir / 'frontend' / 'src' / 'App.jsx'
    if jsx_file.exists():
        lines = len(jsx_file.read_text(encoding='utf-8').split('\n'))
        print(f"✓ frontend/src/App.jsx: {lines} lines")
    else:
        print(f"❌ frontend/src/App.jsx: NOT FOUND")
    
    css_file = app_dir / 'frontend' / 'src' / 'App.css'
    if css_file.exists():
        lines = len(css_file.read_text(encoding='utf-8').split('\n'))
        print(f"✓ frontend/src/App.css: {lines} lines")
    else:
        print(f"❌ frontend/src/App.css: NOT FOUND")
