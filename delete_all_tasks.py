"""
Delete all analysis tasks from the database.
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("Deleting all analysis tasks from database...\n")
    
    # Count tasks before deletion
    total_tasks = AnalysisTask.query.count()
    print(f"Found {total_tasks} tasks to delete")
    
    if total_tasks == 0:
        print("No tasks to delete.")
    else:
        # Confirm deletion
        print(f"\n⚠️  This will permanently delete all {total_tasks} tasks from the database.")
        
        # Delete all tasks
        try:
            deleted_count = AnalysisTask.query.delete()
            db.session.commit()
            print(f"\n✅ Successfully deleted {deleted_count} tasks")
            
            # Verify deletion
            remaining = AnalysisTask.query.count()
            print(f"Remaining tasks: {remaining}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error deleting tasks: {e}")
            import traceback
            traceback.print_exc()
