#!/usr/bin/env python3
"""
Backfill Docker scaffolding files to all generated apps.
Copies all Docker infrastructure files from scaffolding template.
"""

import json
import sys
import shutil
import re
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


def substitute_placeholders(content, substitutions):
    """Replace placeholders in content with actual values."""
    # Handle pipe-default syntax {{key|default}}
    for key, value in substitutions.items():
        pattern = r'\{\{' + re.escape(key) + r'\|[^\}]+\}\}'
        content = re.sub(pattern, str(value), content)
    
    # Handle standard placeholders {{key}}
    for key, value in substitutions.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    
    return content


def scaffold_app(app_dir, model_slug, app_num, backend_port, frontend_port):
    """Copy all scaffolding files to an app directory."""
    scaffolding_src = SCAFFOLDING_DIR / "react-flask"
    
    if not scaffolding_src.exists():
        print(f"❌ Scaffolding directory not found: {scaffolding_src}")
        return False, []
    
    model_prefix = re.sub(r'[^\w\-]', '_', model_slug.lower())
    
    substitutions = {
        'model_name': model_slug,
        'model_name_lower': model_prefix,
        'backend_port': str(backend_port),
        'frontend_port': str(frontend_port),
        'model_prefix': model_prefix,
        'python_version': '3.12',
        'node_version': '20',
        'app_file': 'app.py',
        'server_type': 'flask',
    }
    
    files_copied = []
    files_skipped = []
    
    # Recursively copy all files
    for src in scaffolding_src.rglob('*'):
        if not src.is_file():
            continue
        
        rel = src.relative_to(scaffolding_src)
        
        # Drop .template suffix if present
        target_name = rel.name[:-9] if rel.name.endswith('.template') else rel.name
        target_path = app_dir / rel.parent / target_name
        
        # Check if file exists
        if target_path.exists():
            files_skipped.append(str(rel))
            continue
        
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Read and process template
            content = src.read_text(encoding='utf-8', errors='ignore')
            
            # Determine context-sensitive port
            contextual_port = str(backend_port) if 'backend' in rel.parts else str(frontend_port)
            substitutions['port'] = contextual_port
            
            # Apply substitutions
            content = substitute_placeholders(content, substitutions)
            
            # Write file
            target_path.write_text(content, encoding='utf-8')
            files_copied.append(str(rel))
            
        except Exception as e:
            print(f"  ⚠️  Failed to copy {rel}: {e}")
    
    return True, files_copied


def backfill_all_apps():
    """Backfill Docker scaffolding to all generated apps."""
    
    port_config = load_port_config()
    print(f"✓ Loaded {len(port_config)} port configurations\n")
    
    stats = {
        'checked': 0,
        'scaffolded': 0,
        'files_added': 0,
    }
    
    for model_dir in GENERATED_APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.glob("app*"):
            if not app_dir.is_dir():
                continue
            
            stats['checked'] += 1
            model_slug = model_dir.name
            app_num = int(app_dir.name.replace("app", ""))
            backend_port, frontend_port = get_ports_for_app(port_config, model_slug, app_num)
            
            # Check if scaffolding needed
            critical_files = [
                app_dir / "docker-compose.yml",
                app_dir / "backend" / "Dockerfile",
                app_dir / "frontend" / "Dockerfile"
            ]
            
            missing_files = [f.name for f in critical_files if not f.exists()]
            
            if not missing_files:
                continue
            
            # Scaffold the app
            success, files_copied = scaffold_app(app_dir, model_slug, app_num, backend_port, frontend_port)
            
            if success and files_copied:
                stats['scaffolded'] += 1
                stats['files_added'] += len(files_copied)
                app_path = app_dir.relative_to(GENERATED_APPS_DIR)
                print(f"✓ Scaffolded {app_path}: {len(files_copied)} files added")
                print(f"  Missing: {', '.join(missing_files)}")
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Apps checked: {stats['checked']}")
    print(f"  Apps scaffolded: {stats['scaffolded']}")
    print(f"  Total files added: {stats['files_added']}")
    print(f"{'='*60}")
    
    return True


if __name__ == "__main__":
    print("Backfilling Docker scaffolding to generated apps...")
    print(f"Apps directory: {GENERATED_APPS_DIR}")
    print(f"Scaffolding source: {SCAFFOLDING_DIR / 'react-flask'}\n")
    
    success = backfill_all_apps()
    sys.exit(0 if success else 1)
