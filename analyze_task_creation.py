"""Analyze the pattern of task creation to understand why so many were created."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from sqlalchemy import func, desc
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    print('\n' + '='*70)
    print('ANALYZING TASK CREATION PATTERN')
    print('='*70 + '\n')
    
    # Get all tasks grouped by created date
    tasks_by_date = AnalysisTask.query.with_entities(
        func.date(AnalysisTask.created_at).label('date'),
        func.count(AnalysisTask.id).label('count')
    ).group_by(
        func.date(AnalysisTask.created_at)
    ).order_by(desc('date')).all()
    
    print('Tasks Created Per Day:')
    for date, count in tasks_by_date[:10]:
        print(f'   {date}: {count} tasks')
    
    # Get tasks created in last 24 hours
    yesterday = datetime.now() - timedelta(days=1)
    recent_tasks = AnalysisTask.query.filter(
        AnalysisTask.created_at >= yesterday
    ).order_by(AnalysisTask.created_at.asc()).all()
    
    if recent_tasks:
        print(f'\nLast 24 Hours: {len(recent_tasks)} tasks created')
        
        # Group by target
        by_target = {}
        for task in recent_tasks:
            key = f"{task.target_model}/app{task.target_app_number}"
            by_target[key] = by_target.get(key, 0) + 1
        
        print('\n   Breakdown by target:')
        for target, count in sorted(by_target.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f'     {target}: {count} tasks')
        
        # Check timing - look for rapid creation
        print('\nTask Creation Timing (first 20 recent):')
        prev_time = None
        rapid_count = 0
        for i, task in enumerate(recent_tasks[:20]):
            if prev_time:
                delta = (task.created_at - prev_time).total_seconds()
                if delta < 1:  # Less than 1 second apart
                    rapid_count += 1
                    marker = ' [RAPID]'
                else:
                    marker = ''
                print(f'     {task.created_at} - {task.task_id[:16]}... (delta {delta:.2f}s){marker}')
            else:
                print(f'     {task.created_at} - {task.task_id[:16]}...')
            prev_time = task.created_at
        
        if rapid_count > 0:
            print(f'\n   WARNING: {rapid_count} tasks created within 1 second of each other!')
    
    # Check for any pattern in task names
    print('\nTask Name Patterns:')
    all_tasks = AnalysisTask.query.all()
    name_counts = {}
    for task in all_tasks:
        name_counts[task.task_name] = name_counts.get(task.task_name, 0) + 1
    
    for name, count in sorted(name_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f'   {name}: {count} tasks')
    
    print('\n' + '='*70)
