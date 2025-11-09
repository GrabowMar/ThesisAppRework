"""Clean up orphan app records (database records without filesystem dirs)."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import GeneratedApplication
from app.extensions import db
import os
from pathlib import Path

app = create_app()
with app.app_context():
    # Find all apps in database
    all_apps = GeneratedApplication.query.all()
    
    print(f'\n🔍 Checking {len(all_apps)} apps in database...\n')
    
    orphans = []
    base_path = Path('generated/apps')
    
    for app_record in all_apps:
        app_dir = base_path / app_record.model_slug / f'app{app_record.app_number}'
        
        if not app_dir.exists():
            orphans.append(app_record)
            print(f'  ❌ ORPHAN: {app_record.model_slug}/app{app_record.app_number} (ID: {app_record.id})')
    
    if orphans:
        print(f'\n\n📊 Found {len(orphans)} orphan database records without filesystem directories')
        print(f'\nThese records exist in the database but have no corresponding app directory.')
        print(f'This causes the system to create analysis tasks for non-existent apps.\n')
        
        print(f'Deleting all {len(orphans)} orphan database records...')
        for orphan in orphans:
            db.session.delete(orphan)
        db.session.commit()
        print(f'\n✅ Deleted {len(orphans)} orphan database records')
        print('   Analysis tasks will no longer be created for these non-existent apps.')
    else:
        print('\n✅ No orphan database records found - all apps have corresponding directories!')
