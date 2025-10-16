#!/usr/bin/env python3
"""
Backfill missing vite.config.js files to all generated React apps.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# pylint: disable=wrong-import-position
from app.paths import GENERATED_APPS_DIR, SCAFFOLDING_DIR, MISC_DIR


def load_port_config():
    """Load port configuration from JSON file."""
    port_config_file = MISC_DIR / "port_config.json"
    if not port_config_file.exists():
        return {}
    return json.loads(port_config_file.read_text())


def get_ports_for_app(port_config, model_slug, app_num):
    """Get ports from config or use defaults."""
    key = f"{model_slug}:app{app_num}"
    if key in port_config:
        return port_config[key]["backend"], port_config[key]["frontend"]
    
    # Fallback defaults
    BASE_BACKEND = 5001
    BASE_FRONTEND = 8001
    offset = app_num - 1
    return BASE_BACKEND + (offset * 2), BASE_FRONTEND + (offset * 2)


def backfill_vite_configs():
    """Backfill missing vite.config.js files from scaffolding template."""
    
    # Load the template
    template_path = SCAFFOLDING_DIR / "react-flask" / "frontend" / "vite.config.js"
    if not template_path.exists():
        print(f"❌ Template not found: {template_path}")
        return False
    
    template_content = template_path.read_text(encoding='utf-8')
    print(f"✓ Loaded template from {template_path}")
    
    # Load port configuration
    port_config = load_port_config()
    print(f"✓ Loaded {len(port_config)} port configurations")
    
    # Find all frontend directories
    apps_needing_fix = []
    apps_already_ok = []
    
    for model_dir in GENERATED_APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.glob("app*"):
            if not app_dir.is_dir():
                continue
            
            frontend_dir = app_dir / "frontend"
            if not frontend_dir.exists():
                continue
            
            vite_config = frontend_dir / "vite.config.js"
            
            if vite_config.exists():
                apps_already_ok.append(str(frontend_dir.relative_to(GENERATED_APPS_DIR)))
                continue
            
            # Need to backfill
            model_slug = model_dir.name
            app_num = int(app_dir.name.replace("app", ""))
            
            backend_port, frontend_port = get_ports_for_app(port_config, model_slug, app_num)
            
            # Substitute ports in template
            content = template_content.replace("{{frontend_port|8000}}", str(frontend_port))
            content = content.replace("{{backend_port|5000}}", str(backend_port))
            
            # Write the file
            vite_config.write_text(content, encoding='utf-8')
            apps_needing_fix.append(str(frontend_dir.relative_to(GENERATED_APPS_DIR)))
            print(f"✓ Created {vite_config.relative_to(GENERATED_APPS_DIR)}")
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Apps fixed: {len(apps_needing_fix)}")
    print(f"  Apps already OK: {len(apps_already_ok)}")
    print(f"{'='*60}")
    
    if apps_needing_fix:
        print("\nFixed apps:")
        for app in apps_needing_fix[:10]:  # Show first 10
            print(f"  - {app}")
        if len(apps_needing_fix) > 10:
            print(f"  ... and {len(apps_needing_fix) - 10} more")
    
    return True


if __name__ == "__main__":
    print("Backfilling vite.config.js files...")
    print(f"Apps directory: {GENERATED_APPS_DIR}")
    print(f"Scaffolding: {SCAFFOLDING_DIR}")
    print()
    
    success = backfill_vite_configs()
    sys.exit(0 if success else 1)
