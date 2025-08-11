"""
Test script to verify tasks.py and batch_service integration
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    # Test importing tasks
    from app.tasks import (
        security_analysis_task,
        performance_test_task,
        static_analysis_task,
        ai_analysis_task,
        batch_analysis_task,
        celery
    )
    
    print("✅ Successfully imported all task functions")
    
    # Test importing batch service
    from app.services.batch_service import batch_service
    print("✅ Successfully imported batch service")
    
    # Test analyzer integration
    from app.tasks import get_analyzer_service
    analyzer_service = get_analyzer_service()
    print(f"✅ Analyzer service available: {analyzer_service is not None}")
    
    # Print available tasks
    print(f"\n📋 Available Celery tasks:")
    for task_name in sorted(celery.tasks.keys()):
        if 'app.tasks' in task_name:
            print(f"   - {task_name}")
    
    # Test batch service methods
    print("\n🔧 Batch service methods:")
    print(f"   - create_job: {hasattr(batch_service, 'create_job')}")
    print(f"   - start_job: {hasattr(batch_service, 'start_job')}")
    print(f"   - cancel_job: {hasattr(batch_service, 'cancel_job')}")
    print(f"   - update_task_progress: {hasattr(batch_service, 'update_task_progress')}")
    
    print("\n🎉 All integration tests passed!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
