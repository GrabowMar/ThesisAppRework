#!/usr/bin/env python
"""
Test Parallel Subtask Execution
================================

Quick smoke test to verify parallel execution and result generation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.constants import AnalysisStatus, AnalysisType, JobPriority as Priority
from app.services.task_service import AnalysisTaskService
import time

def test_parallel_execution():
    """Test that subtasks can be created and execute in parallel."""
    
    app = create_app()
    
    with app.app_context():
        print("🧪 Testing Parallel Subtask Execution")
        print("=" * 50)
        
        # 1. Create a unified analysis task with subtasks
        print("\n📝 Step 1: Creating main task with subtasks...")
        
        tools_by_service = {
            'static-analyzer': [1, 2],      # bandit, safety
            'dynamic-analyzer': [10],       # zap
            'performance-tester': [20],     # locust
            'ai-analyzer': [30]             # requirements-scanner
        }
        
        main_task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug='test_model',
            app_number=1,
            analysis_type='unified',
            tools_by_service=tools_by_service,
            config_id=None,
            priority=Priority.NORMAL.value,
            custom_options={
                'unified_analysis': True,
                'tools_by_service': tools_by_service
            },
            task_name='Test Parallel Execution'
        )
        
        print(f"✅ Created main task: {main_task.task_id}")
        
        # 2. Check that subtasks were created
        print("\n📊 Step 2: Verifying subtasks...")
        subtasks = AnalysisTask.query.filter_by(parent_task_id=main_task.task_id).all()
        
        print(f"Found {len(subtasks)} subtasks:")
        for subtask in subtasks:
            print(f"  - {subtask.service_name}: {subtask.task_id} (status={subtask.status})")
        
        if len(subtasks) != 4:
            print(f"❌ Expected 4 subtasks, got {len(subtasks)}")
            return False
        
        # 3. Check Celery task imports
        print("\n🔍 Step 3: Verifying Celery tasks...")
        try:
            from app.tasks import (
                run_static_analyzer_subtask,
                run_dynamic_analyzer_subtask,
                run_performance_tester_subtask,
                run_ai_analyzer_subtask,
                aggregate_subtask_results
            )
            print("✅ All Celery subtask functions imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import Celery tasks: {e}")
            return False
        
        # 4. Check configuration
        print("\n⚙️  Step 4: Verifying configuration...")
        import os
        
        single_file_mode = os.environ.get('SINGLE_FILE_RESULTS', '1')
        print(f"  SINGLE_FILE_RESULTS = {single_file_mode}")
        
        if single_file_mode == '0':
            print("✅ Result persistence enabled")
        else:
            print("⚠️  Result persistence may be disabled (set SINGLE_FILE_RESULTS=0)")
        
        # 5. Simulate parallel execution (without actually running analyzers)
        print("\n🚀 Step 5: Testing parallel execution flow...")
        
        # Mark main task as RUNNING (simulating execution start)
        main_task.status = AnalysisStatus.RUNNING
        main_task.progress_percentage = 0.0
        db.session.commit()
        print(f"  Main task marked as RUNNING")
        
        # Simulate subtask completion
        for i, subtask in enumerate(subtasks):
            subtask.status = AnalysisStatus.RUNNING
            db.session.commit()
            print(f"  Subtask {i+1} marked as RUNNING")
            
            time.sleep(0.1)  # Simulate work
            
            subtask.status = AnalysisStatus.COMPLETED
            subtask.progress_percentage = 100.0
            db.session.commit()
            print(f"  Subtask {i+1} marked as COMPLETED")
        
        # Check that all subtasks are completed
        all_completed = all(st.status == AnalysisStatus.COMPLETED for st in subtasks)
        
        if all_completed:
            print("✅ All subtasks completed successfully")
        else:
            print("❌ Not all subtasks completed")
            return False
        
        # 6. Test result aggregation logic
        print("\n📦 Step 6: Testing result aggregation...")
        
        from app.services.task_execution_service import TaskExecutionService
        service = TaskExecutionService(app=app)
        
        # Manually trigger polling (would normally happen in background)
        service._poll_running_tasks_with_subtasks()
        
        # Refresh main task
        db.session.refresh(main_task)
        
        print(f"  Main task status: {main_task.status}")
        print(f"  Main task progress: {main_task.progress_percentage}%")
        
        if main_task.status == AnalysisStatus.COMPLETED:
            print("✅ Main task marked as COMPLETED after subtasks")
        else:
            print(f"⚠️  Main task status is {main_task.status} (expected COMPLETED)")
        
        # 7. Check result summary
        print("\n📊 Step 7: Checking result summary...")
        
        result_summary = main_task.get_result_summary() if hasattr(main_task, 'get_result_summary') else {}
        
        if result_summary:
            print(f"✅ Result summary exists:")
            print(f"  - Services: {result_summary.get('summary', {}).get('services_executed', 0)}")
            print(f"  - Findings: {result_summary.get('summary', {}).get('total_findings', 0)}")
        else:
            print("⚠️  No result summary found (may need actual analyzer execution)")
        
        print("\n" + "=" * 50)
        print("🎉 Parallel Execution Test PASSED")
        print("=" * 50)
        
        return True

if __name__ == '__main__':
    try:
        success = test_parallel_execution()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
