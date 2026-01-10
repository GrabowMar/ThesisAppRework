#!/usr/bin/env python
"""Quick status check for pipeline and tasks."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask
from app.constants import AnalysisStatus

app = create_app()
with app.app_context():
    pipeline_id = sys.argv[1] if len(sys.argv) > 1 else 'pipeline_680991a2d790'
    pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
    
    if not pipeline:
        print(f'Pipeline {pipeline_id} not found!')
        sys.exit(1)
    
    print(f'Pipeline: {pipeline_id}')
    print(f'  Status: {pipeline.status}')
    print(f'  Stage: {pipeline.current_stage}')
    print(f'  Job Index: {pipeline.current_job_index}')
    
    progress = pipeline.progress
    task_ids = progress.get('analysis', {}).get('task_ids', [])
    print(f'\nAnalysis Tasks: {len(task_ids)}')
    
    for task_id in task_ids:
        if task_id.startswith('skipped') or task_id.startswith('error:'):
            print(f'  {task_id}')
            continue
            
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            print(f'  {task_id}: NOT FOUND')
            continue
            
        subtasks = list(task.subtasks) if task.is_main_task else []
        completed = sum(1 for s in subtasks if s.status == AnalysisStatus.COMPLETED)
        failed = sum(1 for s in subtasks if s.status == AnalysisStatus.FAILED)
        running = sum(1 for s in subtasks if s.status == AnalysisStatus.RUNNING)
        pending = sum(1 for s in subtasks if s.status == AnalysisStatus.PENDING)
        
        print(f'  {task.target_model}/app{task.target_app_number}: {task.status.value}')
        print(f'    Subtasks: done={completed} failed={failed} running={running} pending={pending}')
        
        for s in subtasks:
            status_icon = {'completed': '✓', 'failed': '✗', 'running': '▶', 'pending': '○'}.get(s.status.value, '?')
            error_info = f' - {s.error_message[:60]}...' if s.error_message and len(s.error_message) > 60 else (f' - {s.error_message}' if s.error_message else '')
            print(f'      {status_icon} {s.service_name}: {s.status.value}{error_info}')
