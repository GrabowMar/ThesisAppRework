#!/usr/bin/env python3
"""
Comprehensive repair script for generated applications.
Fixes common generation issues:
1. Missing vite.config.js in frontend
2. Incorrect .jsx references in index.html
3. Missing config.py in backend
"""

import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# pylint: disable=wrong-import-position
from app.paths import GENERATED_APPS_DIR, SCAFFOLDING_DIR, MISC_DIR
import json


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


def fix_vite_config(frontend_dir, backend_port, frontend_port):
    """Add missing vite.config.js."""
    vite_config = frontend_dir / "vite.config.js"
    if vite_config.exists():
        return False
    
    template_path = SCAFFOLDING_DIR / "react-flask" / "frontend" / "vite.config.js"
    if not template_path.exists():
        return False
    
    content = template_path.read_text(encoding='utf-8')
    content = content.replace("{{frontend_port|8000}}", str(frontend_port))
    content = content.replace("{{backend_port|5000}}", str(backend_port))
    vite_config.write_text(content, encoding='utf-8')
    return True


def fix_jsx_reference(frontend_dir):
    """Fix .jsx reference in index.html if main.js exists."""
    index_html = frontend_dir / "index.html"
    if not index_html.exists():
        return False
    
    content = index_html.read_text(encoding='utf-8')
    
    if '/src/main.jsx' in content:
        main_js = frontend_dir / "src" / "main.js"
        main_jsx = frontend_dir / "src" / "main.jsx"
        
        if main_js.exists() and not main_jsx.exists():
            content = content.replace('/src/main.jsx', '/src/main.js')
            index_html.write_text(content, encoding='utf-8')
            return True
    
    return False


def fix_missing_config(backend_dir):
    """Create minimal config.py if missing."""
    config_py = backend_dir / "config.py"
    if config_py.exists():
        return False
    
    # Create minimal config
    config_content = '''"""
Flask configuration module.
"""

import os


class Config:
    """Base configuration."""
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CORS settings
    CORS_HEADERS = 'Content-Type'
    
    # Additional settings
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    TESTING = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
'''
    
    config_py.write_text(config_content, encoding='utf-8')
    return True


def repair_all_apps():
    """Repair all generated applications."""
    
    port_config = load_port_config()
    print(f"✓ Loaded {len(port_config)} port configurations\n")
    
    stats = {
        'checked': 0,
        'vite_config_fixed': 0,
        'jsx_ref_fixed': 0,
        'config_py_fixed': 0,
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
            
            app_path = app_dir.relative_to(GENERATED_APPS_DIR)
            fixes = []
            
            # Fix frontend issues
            frontend_dir = app_dir / "frontend"
            if frontend_dir.exists():
                if fix_vite_config(frontend_dir, backend_port, frontend_port):
                    stats['vite_config_fixed'] += 1
                    fixes.append("vite.config.js")
                
                if fix_jsx_reference(frontend_dir):
                    stats['jsx_ref_fixed'] += 1
                    fixes.append("jsx reference")
            
            # Fix backend issues
            backend_dir = app_dir / "backend"
            if backend_dir.exists():
                if fix_missing_config(backend_dir):
                    stats['config_py_fixed'] += 1
                    fixes.append("config.py")
            
            if fixes:
                print(f"✓ Fixed {app_path}: {', '.join(fixes)}")
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Apps checked: {stats['checked']}")
    print(f"  vite.config.js added: {stats['vite_config_fixed']}")
    print(f"  .jsx references fixed: {stats['jsx_ref_fixed']}")
    print(f"  config.py added: {stats['config_py_fixed']}")
    print(f"  Total fixes: {sum(v for k, v in stats.items() if k != 'checked')}")
    print(f"{'='*60}")
    
    return True


if __name__ == "__main__":
    print("Repairing generated applications...")
    print(f"Apps directory: {GENERATED_APPS_DIR}")
    print(f"Scaffolding: {SCAFFOLDING_DIR}\n")
    
    success = repair_all_apps()
    sys.exit(0 if success else 1)
