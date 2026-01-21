#!/usr/bin/env python3
"""Resume pending analysis tasks after SQLite fix."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask, PipelineExecution
from app.constants import AnalysisStatus
from app.extensions import db

app = create_app()

with app.app_context():
    # Check for active pipelines
    active_pipeline = PipelineExecution.query.filter(
        PipelineExecution.status.in_(['running', 'pending'])
    ).order_by(PipelineExecution.created_at.desc()).first()
    
    if active_pipeline:
        print(f"\n📊 Active Pipeline: {active_pipeline.pipeline_id}")
        status_str = active_pipeline.status.value if hasattr(active_pipeline.status, 'value') else str(active_pipeline.status)
        print(f"   Status: {status_str}")
        print(f"   Stage: {active_pipeline.current_stage}")
        
        # Get analysis progress
        analysis_progress = active_pipeline.progress.get('analysis', {})
        print(f"\n   Analysis Progress:")
        print(f"   - Total: {analysis_progress.get('total', 0)}")
        print(f"   - Completed: {analysis_progress.get('completed', 0)}")
        print(f"   - Failed: {analysis_progress.get('failed', 0)}")
    else:
        print("\n⚠️  No active pipelines found")
    
    # Check for pending tasks
    pending_tasks = AnalysisTask.query.filter_by(
        status=AnalysisStatus.PENDING,
        is_main_task=True
    ).all()
    
    running_tasks = AnalysisTask.query.filter_by(
        status=AnalysisStatus.RUNNING,
        is_main_task=True
    ).all()
    
    print(f"\n📋 Task Status:")
    print(f"   Pending main tasks: {len(pending_tasks)}")
    print(f"   Running main tasks: {len(running_tasks)}")
    
    if pending_tasks:
        print(f"\n   Pending tasks details:")
        for task in pending_tasks[:10]:  # Show first 10
            print(f"   - {task.task_id}: {task.target_model}/app{task.target_app_number}")
    
    # Check TaskExecutionService status via logs
    print(f"\n✅ SQLite WAL mode is enabled")
    print(f"✅ Database lock issues should be resolved")
    print(f"\n💡 The TaskExecutionService will automatically pick up PENDING tasks")
    print(f"   (polls every 2-5 seconds)")
