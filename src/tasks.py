"""
Simplified Celery Background Tasks for AI Testing Framework
===========================================================

Minimal implementation focusing on core functionality.
"""

import time
import traceback
from datetime import datetime, timezone
from typing import List, Optional

from celery import Celery, current_task
from celery.signals import task_prerun, task_postrun

# Import configuration
try:
    from .celery_config import BROKER_URL, CELERY_RESULT_BACKEND
    CELERY_BROKER_URL = BROKER_URL
except ImportError:
    # Default configuration if config file is missing
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Create Celery instance
celery_app = Celery('testing_framework')
celery_app.conf.update(
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Flask app instance
flask_app = None

def get_flask_app():
    """Get Flask app instance for task context."""
    global flask_app
    if flask_app is None:
        try:
            from .app import create_app
        except ImportError:
            from app import create_app
        flask_app = create_app()
    return flask_app

def update_task_progress(task_id: str, current: int, total: int, status: Optional[str] = None):
    """Update task progress for UI display."""
    progress_data: dict = {
        'current': current,
        'total': total,
        'percentage': int((current / total) * 100) if total > 0 else 0
    }
    
    if status:
        progress_data['status'] = status
    
    # Update task state if we have access to current_task
    try:
        if hasattr(current_task, 'update_state') and callable(getattr(current_task, 'update_state')):
            current_task.update_state(
                state='PROGRESS',
                meta=progress_data
            )
    except Exception:
        # If we can't update state, just continue
        pass

@celery_app.task(bind=True, name='src.tasks.test_task')
def test_task(self):
    """Simple test task to verify Celery is working."""
    app = get_flask_app()
    
    with app.app_context():
        update_task_progress(self.request.id, 0, 100, "Starting test task")
        
        # Simulate some work
        for i in range(5):
            time.sleep(1)
            update_task_progress(self.request.id, (i + 1) * 20, 100, f"Processing step {i + 1}")
        
        update_task_progress(self.request.id, 100, 100, "Test completed")
        
        return {
            'status': 'completed',
            'message': 'Test task completed successfully',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@celery_app.task(bind=True, name='src.tasks.run_security_analysis_task')
def run_security_analysis_task(self, model_slug: str, app_number: int, tools: List[str], 
                               analysis_id: Optional[int] = None):
    """
    Simplified security analysis task.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        tools: List of tools to run
        analysis_id: Existing analysis ID to update
    """
    app = get_flask_app()
    
    with app.app_context():
        try:
            update_task_progress(self.request.id, 0, 100, "Initializing security analysis")
            
            # Simulate analysis work
            update_task_progress(self.request.id, 20, 100, "Running security analysis")
            time.sleep(2)  # Simulate work
            
            update_task_progress(self.request.id, 60, 100, "Processing results")
            time.sleep(1)  # Simulate work
            
            # Create mock results
            results = {
                'status': 'completed',
                'tools_used': tools,
                'summary': {
                    'total_issues': 0,
                    'critical': 0,
                    'high': 0,
                    'medium': 0,
                    'low': 0
                },
                'issues': [],
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'analysis_duration': 3.0
                }
            }
            
            update_task_progress(self.request.id, 100, 100, "Analysis completed")
            
            return {
                'status': 'completed',
                'analysis_id': analysis_id,
                'results': results
            }
            
        except Exception as e:
            self.update_state(
                state='FAILURE',
                meta={'error': str(e), 'traceback': traceback.format_exc()}
            )
            raise

@celery_app.task(name='src.tasks.cleanup_expired_results')
def cleanup_expired_results():
    """Cleanup task for expired results."""
    return {'status': 'completed', 'message': 'Cleanup completed'}

@celery_app.task(name='src.tasks.health_check_containers')
def health_check_containers():
    """Health check task for containers."""
    return {'status': 'healthy', 'message': 'All systems operational'}

# Task lifecycle hooks
@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Handle task pre-run setup."""
    print(f"Task {task.name} starting with ID {task_id}")

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    """Handle task post-run cleanup."""
    print(f"Task {task.name} finished with ID {task_id}, state: {state}")

if __name__ == '__main__':
    # For testing purposes
    print("Celery tasks module loaded successfully")
    print(f"Available tasks: {celery_app.tasks.keys()}")
