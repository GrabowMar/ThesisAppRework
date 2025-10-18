"""Automatic Dependency Fixer for Generated Apps
==============================================

Scans generated app.py files, detects all imports, and ensures they're
in requirements.txt with proper versions.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


# Mapping of import names to PyPI package names and versions
PACKAGE_MAPPING = {
    # Standard library (skip these)
    'os': None,
    'sys': None,
    'json': None,
    'logging': None,
    'datetime': None,
    'time': None,
    'base64': None,
    're': None,
    'io': None,
    'pathlib': None,
    'urllib': None,
    'http': None,
    'collections': None,
    'functools': None,
    'itertools': None,
    'typing': None,
    'dataclasses': None,
    'enum': None,
    'traceback': None,
    'warnings': None,
    
    # Flask ecosystem
    'flask': 'Flask==3.0.0',
    'flask_cors': 'Flask-CORS==4.0.0',
    'flask_sqlalchemy': 'Flask-SQLAlchemy==3.1.1',
    'flask_migrate': 'Flask-Migrate==4.0.5',
    'flask_limiter': 'Flask-Limiter==3.5.0',
    'flask_compress': 'Flask-Compress==1.14',
    'flask_caching': 'Flask-Caching==2.1.0',
    'flask_jwt_extended': 'Flask-JWT-Extended==4.6.0',
    'flask_mail': 'Flask-Mail==0.9.1',
    'flask_login': 'Flask-Login==0.6.3',
    'werkzeug': 'Werkzeug==3.0.1',
    'sqlalchemy': 'SQLAlchemy==2.0.25',
    
    # Common libraries
    'lxml': 'lxml==5.1.0',
    'requests': 'requests==2.31.0',
    'bcrypt': 'bcrypt==4.1.2',
    'jwt': 'PyJWT==2.8.0',
    'pyjwt': 'PyJWT==2.8.0',
    'pillow': 'Pillow==10.2.0',
    'pandas': 'pandas==2.2.0',
    'numpy': 'numpy==1.26.3',
    'scipy': 'scipy==1.12.0',
    'matplotlib': 'matplotlib==3.8.2',
    'cryptography': 'cryptography==42.0.0',
    'celery': 'celery==5.3.4',
    'redis': 'redis==5.0.1',
    'dotenv': 'python-dotenv==1.0.0',
    'pymongo': 'pymongo==4.6.1',
    'psycopg2': 'psycopg2-binary==2.9.9',
    'mysql': 'mysql-connector-python==8.2.0',
    'boto3': 'boto3==1.34.34',
    'stripe': 'stripe==7.10.0',
    'sendgrid': 'sendgrid==6.11.0',
    'twilio': 'twilio==8.11.1',
    'openai': 'openai==1.10.0',
    'anthropic': 'anthropic==0.8.1',
    'beautifulsoup4': 'beautifulsoup4==4.12.3',
    'selenium': 'selenium==4.17.2',
    'pytz': 'pytz==2024.1',
    'dateutil': 'python-dateutil==2.8.2',
    'yaml': 'PyYAML==6.0.1',
    'toml': 'toml==0.10.2',
    'xmltodict': 'xmltodict==0.13.0',
    'markdown': 'Markdown==3.5.2',
    'bleach': 'bleach==6.1.0',
}


def extract_imports_from_python(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file."""
    
    imports = set()
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Pattern 1: import module
        for match in re.finditer(r'^import\s+(\w+)', content, re.MULTILINE):
            imports.add(match.group(1))
        
        # Pattern 2: from module import ...
        for match in re.finditer(r'^from\s+(\w+)', content, re.MULTILINE):
            imports.add(match.group(1))
        
        # Pattern 3: from package.module import ...
        for match in re.finditer(r'^from\s+(\w+)\.\w+', content, re.MULTILINE):
            imports.add(match.group(1))
    
    except Exception as e:
        logger.error(f"Failed to extract imports from {file_path}: {e}")
    
    return imports


def get_required_packages(imports: Set[str]) -> Tuple[List[str], List[str]]:
    """Convert imports to required packages with versions."""
    
    packages = []
    missing = []
    
    for imp in sorted(imports):
        # Skip standard library
        if imp in PACKAGE_MAPPING and PACKAGE_MAPPING[imp] is None:
            continue
        
        # Known package
        if imp in PACKAGE_MAPPING:
            packages.append(PACKAGE_MAPPING[imp])
        else:
            # Unknown package - add it anyway with a note
            missing.append(imp)
            logger.warning(f"Unknown import '{imp}' - may need manual package name mapping")
    
    return packages, missing


def fix_requirements_txt(app_dir: Path) -> Tuple[bool, str]:
    """Fix requirements.txt for a backend app."""
    
    backend_dir = app_dir / 'backend'
    app_py = backend_dir / 'app.py'
    requirements_txt = backend_dir / 'requirements.txt'
    
    if not app_py.exists():
        return False, "app.py not found"
    
    # Extract imports
    imports = extract_imports_from_python(app_py)
    logger.info(f"Found {len(imports)} imports in {app_py}")
    
    # Get required packages
    packages, missing = get_required_packages(imports)
    
    if not packages:
        return True, "No packages needed"
    
    # Read existing requirements
    existing = set()
    if requirements_txt.exists():
        content = requirements_txt.read_text(encoding='utf-8')
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (before ==)
                pkg_name = line.split('==')[0].strip()
                existing.add(pkg_name)
    
    # Add missing packages
    new_packages = []
    for pkg in packages:
        pkg_name = pkg.split('==')[0]
        if pkg_name not in existing:
            new_packages.append(pkg)
    
    if new_packages:
        # Append to requirements.txt
        with open(requirements_txt, 'a', encoding='utf-8') as f:
            f.write('\n# Auto-detected dependencies\n')
            for pkg in new_packages:
                f.write(f'{pkg}\n')
        
        logger.info(f"Added {len(new_packages)} packages to requirements.txt")
        message = f"Added {len(new_packages)} packages: {', '.join(new_packages)}"
        
        if missing:
            message += f"\nWarning: Unknown imports (may need manual addition): {', '.join(missing)}"
        
        return True, message
    
    return True, "All packages already in requirements.txt"


def scan_and_fix_all_apps(base_dir: Path) -> Dict[str, Tuple[bool, str]]:
    """Scan all generated apps and fix requirements.txt."""
    
    results = {}
    
    for model_dir in base_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            app_path = f"{model_dir.name}/{app_dir.name}"
            logger.info(f"Checking {app_path}...")
            
            success, message = fix_requirements_txt(app_dir)
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
    
    print("Scanning generated apps for missing dependencies...")
    print("=" * 60)
    
    results = scan_and_fix_all_apps(GENERATED_APPS_DIR)
    
    print("\nResults:")
    print("=" * 60)
    
    for app_path, (success, message) in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {app_path}")
        if message:
            print(f"  {message}")
    
    print(f"\nProcessed {len(results)} apps")


if __name__ == "__main__":
    main()
