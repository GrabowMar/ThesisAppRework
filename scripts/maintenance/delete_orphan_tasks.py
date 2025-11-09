"""Delete all tasks for app4658 since the app doesn't exist anymore."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    # Delete all tasks for the orphan app
    orphan_tasks = AnalysisTask.query.filter_by(
        target_model='openai_codex-mini',
        target_app_number=4658
    ).all()
    
    print(f'\n🗑️  Deleting {len(orphan_tasks)} tasks for openai_codex-mini/app4658...')
    
    for task in orphan_tasks:
        db.session.delete(task)
    
    db.session.commit()
    
    print(f'✅ Deleted {len(orphan_tasks)} orphan tasks')
    
    # Verify
    remaining = AnalysisTask.query.filter_by(
        target_model='openai_codex-mini',
        target_app_number=4658
    ).count()
    
    print(f'\n📊 Remaining tasks for app4658: {remaining}')
