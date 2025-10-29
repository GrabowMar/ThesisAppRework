"""Check what generated applications exist in database vs filesystem."""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from app.factory import create_app
from app.models import GeneratedApplication

app = create_app()

with app.app_context():
    # Get all generated applications from database
    apps = GeneratedApplication.query.all()
    
    print("=" * 80)
    print("GENERATED APPLICATIONS IN DATABASE")
    print("=" * 80)
    print()
    
    if not apps:
        print("No generated applications found in database!")
    else:
        print(f"Found {len(apps)} application(s) in database:\n")
        
        for app_record in apps:
            print(f"Model: {app_record.model_slug}")
            print(f"  App Number: {app_record.app_number}")
            print(f"  Created: {app_record.created_at}")
            print(f"  Template ID: {app_record.template_id}")
            
            # Check if path exists on filesystem
            from app.paths import GENERATED_APPS_DIR
            app_dir = Path(GENERATED_APPS_DIR) / app_record.model_slug / f"app{app_record.app_number}"
            exists = app_dir.exists()
            print(f"  Path exists: {exists}")
            print(f"  Path: {app_dir}")
            
            # List files if exists
            if exists:
                files = list(app_dir.rglob("*"))
                print(f"  Files: {len([f for f in files if f.is_file()])}")
                print(f"  Dirs: {len([f for f in files if f.is_dir()])}")
            print()
