import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from pathlib import Path

app = create_app()
with app.app_context():
    tasks_with_0 = AnalysisTask.query.filter_by(
        is_main_task=True, 
        issues_found=0, 
        status='completed'
    ).order_by(AnalysisTask.created_at.desc()).limit(15).all()
    
    print(f'Recent completed main tasks with 0 issues: {len(tasks_with_0)}\n')
    
    for t in tasks_with_0:
        # Check if has service files with SARIF
        task_dir = Path('results') / t.target_model / f'app{t.target_app_number}' / t.task_id
        has_services = (task_dir / 'services').exists() if task_dir.exists() else False
        has_sarif = (task_dir / 'sarif').exists() if task_dir.exists() else False
        
        print(f'{t.task_id}:')
        print(f'  Model: {t.target_model} app{t.target_app_number}')
        print(f'  Created: {t.created_at.strftime("%Y-%m-%d %H:%M")}')
        print(f'  Has services/: {has_services}')
        print(f'  Has sarif/: {has_sarif}')
        print()
