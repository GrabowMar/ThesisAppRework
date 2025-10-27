"""Check analysis task statuses in database"""
import sys
import os
from pathlib import Path

# Add src directory to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
src_dir = project_root / 'src'
sys.path.insert(0, str(src_dir))

# Prevent Flask from starting in debug mode
os.environ['WERKZEUG_RUN_MAIN'] = 'true'
os.environ['FLASK_DEBUG'] = '0'

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from datetime import datetime, timedelta

# Create app without running server
app = create_app()
app.config['TESTING'] = True

with app.app_context():
    # Get recent tasks for openai_codex-mini
    recent_cutoff = datetime.utcnow() - timedelta(hours=3)
    tasks = AnalysisTask.query.filter(
        AnalysisTask.target_model == 'openai_codex-mini',
        AnalysisTask.created_at >= recent_cutoff
    ).order_by(AnalysisTask.created_at.desc()).all()
    
    print(f'\n=== Found {len(tasks)} recent tasks for openai_codex-mini ===\n')
    
    main_tasks = [t for t in tasks if t.is_main_task]
    subtasks = [t for t in tasks if not t.is_main_task]
    
    print(f'Main tasks: {len(main_tasks)}')
    print(f'Subtasks: {len(subtasks)}\n')
    
    for task in main_tasks:
        status_val = task.status.value if hasattr(task.status, 'value') else str(task.status)
        print(f'MAIN: {task.task_id[:12]}... | App{task.target_app_number} | {task.analysis_type} | Status: {status_val}')
        print(f'      Created: {task.created_at.strftime("%H:%M:%S")}')
        print(f'      Steps: {task.completed_steps}/{task.total_steps}')
        if task.error_message:
            print(f'      ERROR: {task.error_message[:100]}')
        
        # Find subtasks
        task_subtasks = [st for st in subtasks if st.parent_task_id == task.task_id]
        for st in task_subtasks:
            st_status = st.status.value if hasattr(st.status, 'value') else str(st.status)
            print(f'      └─ {st.service_name}: {st_status}', end='')
            if st.error_message:
                print(f' (ERROR: {st.error_message[:50]}...)')
            else:
                print()
        print()
