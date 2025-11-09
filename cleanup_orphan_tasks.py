"""Clean up orphan analysis tasks for non-existent apps."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask, GeneratedApplication, AnalysisStatus
from app.extensions import db

app = create_app()
with app.app_context():
    # Find all PENDING tasks
    pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).all()
    
    print(f'\n Found {len(pending_tasks)} PENDING tasks total')
    
    orphaned = []
    for task in pending_tasks:
        # Check if the target app exists
        app_exists = GeneratedApplication.query.filter_by(
            model_slug=task.target_model,
            app_number=task.target_app_number
        ).first()
        
        if not app_exists:
            orphaned.append(task)
    
    print(f'\nFound {len(orphaned)} orphan tasks targeting non-existent apps')
    
    if orphaned:
        print('\nSample orphan tasks:')
        for t in orphaned[:10]:
            print(f'  {t.task_id}: {task.target_model}/app{task.target_app_number} - {t.task_name}')
        
        response = input(f'\nDelete all {len(orphaned)} orphan PENDING tasks? (yes/no): ')
        if response.lower() == 'yes':
            for task in orphaned:
                db.session.delete(task)
            db.session.commit()
            print(f'\n✅ Deleted {len(orphaned)} orphan tasks')
        else:
            print('\n❌ Cancelled - no tasks deleted')
    else:
        print('\n✅ No orphan tasks found!')
