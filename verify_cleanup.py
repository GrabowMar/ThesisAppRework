"""Verify cleanup - check for any remaining issues."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask, GeneratedApplication, AnalysisStatus
from pathlib import Path

app = create_app()
with app.app_context():
    print('\n' + '='*60)
    print('🔍 POST-CLEANUP VERIFICATION')
    print('='*60 + '\n')
    
    # 1. Check for orphan app records
    all_apps = GeneratedApplication.query.all()
    base_path = Path('generated/apps')
    orphan_apps = []
    
    for app_record in all_apps:
        app_dir = base_path / app_record.model_slug / f'app{app_record.app_number}'
        if not app_dir.exists():
            orphan_apps.append(app_record)
    
    print(f'1️⃣  Orphan App Records: {len(orphan_apps)}')
    if orphan_apps:
        for app_rec in orphan_apps[:5]:
            print(f'   ❌ {app_rec.model_slug}/app{app_rec.app_number}')
    else:
        print('   ✅ No orphan app records found!')
    
    # 2. Check for PENDING tasks
    pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).all()
    print(f'\n2️⃣  PENDING Tasks: {len(pending_tasks)}')
    if pending_tasks:
        for task in pending_tasks[:5]:
            print(f'   ⏳ {task.task_id}: {task.target_model}/app{task.target_app_number}')
    else:
        print('   ✅ No pending tasks!')
    
    # 3. Check for RUNNING tasks
    running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
    print(f'\n3️⃣  RUNNING Tasks: {len(running_tasks)}')
    if running_tasks:
        for task in running_tasks[:5]:
            print(f'   🏃 {task.task_id}: {task.target_model}/app{task.target_app_number}')
    else:
        print('   ✅ No running tasks!')
    
    # 4. Summary
    print('\n' + '='*60)
    print('📊 SUMMARY')
    print('='*60)
    print(f'  Total apps in DB: {len(all_apps)}')
    print(f'  Orphan apps: {len(orphan_apps)}')
    print(f'  PENDING tasks: {len(pending_tasks)}')
    print(f'  RUNNING tasks: {len(running_tasks)}')
    
    if len(orphan_apps) == 0 and len(pending_tasks) == 0 and len(running_tasks) == 0:
        print('\n✅ ALL CLEAN! No orphan records or stuck tasks.')
    else:
        print('\n⚠️  Some issues remain - see details above.')
    print('='*60 + '\n')
