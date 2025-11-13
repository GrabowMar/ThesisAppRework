#!/usr/bin/env python3
"""Test automatic sync of generated apps on startup"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.models import GeneratedApplication
from app.extensions import db

def test_auto_sync():
    """Test that apps are auto-synced on startup"""
    print("=" * 70)
    print("TESTING AUTO-SYNC ON APP STARTUP")
    print("=" * 70)
    
    # Create app - this should trigger auto-sync
    print("\nCreating app (should trigger auto-sync)...")
    app = create_app()
    
    with app.app_context():
        # Check GeneratedApplication table
        apps = GeneratedApplication.query.all()
        
        print(f"\nGeneratedApplication records: {len(apps)}")
        
        if apps:
            print("\n✅ Apps found in database:")
            
            # Group by model
            apps_by_model = {}
            for app_record in apps:
                if app_record.model_slug not in apps_by_model:
                    apps_by_model[app_record.model_slug] = []
                apps_by_model[app_record.model_slug].append(app_record.app_number)
            
            for model_slug, app_numbers in sorted(apps_by_model.items()):
                print(f"  • {model_slug}: {sorted(app_numbers)}")
            
            print(f"\n✅ SUCCESS: {len(apps)} apps synced automatically!")
        else:
            print("\n⚠️ No apps found - check if generated/apps/ has any apps")
            
            # Check filesystem
            from pathlib import Path
            project_root = Path(app.root_path).parent.parent
            generated_apps_dir = project_root / 'generated' / 'apps'
            
            if generated_apps_dir.exists():
                model_dirs = [d for d in generated_apps_dir.iterdir() if d.is_dir()]
                print(f"\nFilesystem check: {len(model_dirs)} model directories found")
                
                for model_dir in model_dirs[:5]:  # Show first 5
                    app_dirs = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
                    print(f"  • {model_dir.name}: {len(app_dirs)} apps")
            else:
                print(f"\n❌ Directory not found: {generated_apps_dir}")

if __name__ == '__main__':
    test_auto_sync()
