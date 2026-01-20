"""
Test to verify pipeline completion check considers remaining jobs.

This test verifies the fix for the bug where pipelines would complete
prematurely when all submitted tasks finished but more jobs remained.
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution
from datetime import datetime, timezone

def test_completion_check():
    """Test that pipeline doesn't complete with remaining jobs."""
    app = create_app()
    
    with app.app_context():
        # Create a mock pipeline with 10 expected jobs but only 6 submitted
        pipeline = PipelineExecution(
            user_id=1,
            name="Test Pipeline",
            config={
                'generation': {
                    'mode': 'generate',
                    'models': ['test_model'],
                    'templates': ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10']
                },
                'analysis': {
                    'enabled': True,
                    'tools': ['semgrep', 'bandit']
                }
            }
        )
        
        # Simulate 10 generation results
        pipeline.progress = {
            'generation': {
                'total': 10,
                'completed': 10,
                'failed': 0,
                'status': 'completed',
                'results': [
                    {'job_index': i, 'model_slug': 'test_model', 'app_number': i+1, 'success': True}
                    for i in range(10)
                ]
            },
            'analysis': {
                'total': 10,
                'completed': 6,
                'failed': 0,
                'main_task_ids': [f'task_{i}' for i in range(6)],  # Only 6 tasks
                'submitted_apps': [f'test_model:{i+1}' for i in range(6)]
            }
        }
        
        # Simulate we're at job_index 6 (submitted 6, need 10)
        pipeline.current_job_index = 6
        pipeline.current_stage = 'analysis'
        
        # Import the service
        from app.services.pipeline_execution_service import PipelineExecutionService
        service = PipelineExecutionService()
        
        # Test the completion check
        # Should return False because jobs_remaining = 10 - 6 = 4
        is_complete = service._check_analysis_tasks_completion(pipeline)
        
        print(f"Pipeline job_index: {pipeline.current_job_index}")
        print(f"Expected jobs: 10")
        print(f"Jobs remaining: {10 - pipeline.current_job_index}")
        print(f"Main tasks created: {len(pipeline.progress['analysis']['main_task_ids'])}")
        print(f"Completion check returned: {is_complete}")
        
        if is_complete:
            print("\n[FAIL] Pipeline marked as complete with 4 jobs remaining!")
            return False
        else:
            print("\n[PASS] Pipeline correctly remains running with jobs to submit")
            return True

if __name__ == '__main__':
    success = test_completion_check()
    sys.exit(0 if success else 1)
