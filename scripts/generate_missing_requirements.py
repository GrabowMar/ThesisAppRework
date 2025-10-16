"""
Generate missing requirements.txt files for generated apps.

Scans all generated applications and creates requirements.txt files
in backend directories that are missing them.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from app.paths import GENERATED_APPS_DIR


def get_default_flask_requirements() -> str:
    """Return default Flask requirements for backend apps."""
    return """# Flask Backend Requirements
Flask==3.0.0
Flask-CORS==4.0.0
Flask-SQLAlchemy==3.1.1
Werkzeug==3.0.1
python-dotenv==1.0.0
requests==2.31.0
"""


def get_default_react_requirements() -> str:
    """Return default dependencies for React frontend (package.json)."""
    # Note: This is for future use if we need to generate package.json
    return """{
  "name": "frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8"
  }
}
"""


def scan_and_generate_requirements():
    """Scan all generated apps and create missing requirements.txt and package.json files."""
    if not GENERATED_APPS_DIR.exists():
        print(f"❌ Generated apps directory not found: {GENERATED_APPS_DIR}")
        return

    stats = {
        'scanned_backend': 0,
        'scanned_frontend': 0,
        'missing_backend': 0,
        'missing_frontend': 0,
        'created_backend': 0,
        'created_frontend': 0,
        'errors': 0
    }

    print("🔍 Scanning for missing dependency files...")
    print(f"   Base directory: {GENERATED_APPS_DIR}\n")

    # Iterate through all model directories
    for model_dir in sorted(GENERATED_APPS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue

        # Iterate through app directories
        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue

            # Check backend
            backend_dir = app_dir / 'backend'
            if backend_dir.exists():
                stats['scanned_backend'] += 1
                requirements_file = backend_dir / 'requirements.txt'

                if not requirements_file.exists():
                    stats['missing_backend'] += 1
                    print(f"📝 Missing: {model_dir.name}/{app_dir.name}/backend/requirements.txt")

                    try:
                        # Create requirements.txt with default content
                        requirements_file.write_text(get_default_flask_requirements(), encoding='utf-8')
                        stats['created_backend'] += 1
                        print("   ✅ Created requirements.txt")
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"   ❌ Error creating file: {e}")

            # Check frontend
            frontend_dir = app_dir / 'frontend'
            if frontend_dir.exists():
                stats['scanned_frontend'] += 1
                package_file = frontend_dir / 'package.json'

                if not package_file.exists():
                    stats['missing_frontend'] += 1
                    print(f"📝 Missing: {model_dir.name}/{app_dir.name}/frontend/package.json")

                    try:
                        # Create package.json with default content
                        package_file.write_text(get_default_react_requirements(), encoding='utf-8')
                        stats['created_frontend'] += 1
                        print("   ✅ Created package.json")
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"   ❌ Error creating file: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("📊 Summary:")
    print(f"   Backend directories scanned: {stats['scanned_backend']}")
    print(f"   Frontend directories scanned: {stats['scanned_frontend']}")
    print(f"   Missing requirements.txt: {stats['missing_backend']}")
    print(f"   Missing package.json: {stats['missing_frontend']}")
    print(f"   Created requirements.txt: {stats['created_backend']}")
    print(f"   Created package.json: {stats['created_frontend']}")
    if stats['errors'] > 0:
        print(f"   ⚠️  Errors: {stats['errors']}")
    print(f"{'='*60}")

    total_created = stats['created_backend'] + stats['created_frontend']
    if total_created > 0:
        print(f"\n✅ Generated {total_created} missing dependency file(s)")
        print("   Apps are now ready for containerization!")
    elif stats['missing_backend'] == 0 and stats['missing_frontend'] == 0:
        print("\n✅ All apps already have dependency files")
    else:
        total_missing = stats['missing_backend'] + stats['missing_frontend']
        print(f"\n⚠️  {total_missing} file(s) still missing due to errors")


if __name__ == '__main__':
    scan_and_generate_requirements()
