#!/usr/bin/env python3
"""
Test script to debug the analysis integration.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.services.task_service import AnalysisTaskService

def test_analysis_integration():
    """Test the analysis integration with the analyzer services."""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Testing Analysis Integration")
        print("=" * 60)
        
        # Test 1: Create an analysis task
        print("1. Creating analysis task...")
        try:
            task = AnalysisTaskService.create_task(
                model_slug='nousresearch_hermes-4-405b',
                app_number=1,
                analysis_type='security_backend',
                priority='normal'
            )
            print(f"   ✅ Created task: {task.task_id}")
            print(f"   📋 Model: {task.target_model}")
            print(f"   📋 App: {task.target_app_number}")
            print(f"   📋 Type: {task.analysis_type}")
            print(f"   📋 Status: {task.status}")
        except Exception as e:
            print(f"   ❌ Failed to create task: {e}")
            return
        
        # Test 2: Check task statistics
        print("\n2. Getting task statistics...")
        try:
            stats = AnalysisTaskService.get_task_statistics()
            print(f"   📊 Total tasks: {stats['total_tasks']}")
            print(f"   📊 Status counts: {stats['status_counts']}")
            print(f"   📊 Active tasks: {stats['active_tasks']}")
        except Exception as e:
            print(f"   ❌ Failed to get stats: {e}")
        
        # Test 3: Test analyzer direct execution
        print("\n3. Testing direct analyzer execution...")
        try:
            # Import the task function and run it directly (bypassing Celery)
            from app.tasks import security_analysis_task
            
            print("   🔄 Running security analysis task...")
            result = security_analysis_task.run(
                'nousresearch_hermes-4-405b', 
                1, 
                tools=['bandit', 'safety', 'pylint']
            )
            
            print("   ✅ Analysis completed!")
            print(f"   📋 Status: {result.get('status', 'unknown')}")
            print(f"   📋 Model: {result.get('model_slug')}")
            print(f"   📋 App: {result.get('app_number')}")
            
            if 'result' in result and isinstance(result['result'], dict):
                analysis_result = result['result']
                print(f"   📋 Analysis status: {analysis_result.get('status', 'unknown')}")
                
                if 'results' in analysis_result:
                    results = analysis_result['results']
                    if 'analysis' in results:
                        analysis_data = results['analysis']
                        if 'summary' in analysis_data:
                            summary = analysis_data['summary']
                            print(f"   📊 Total issues: {summary.get('total_issues_found', 0)}")
                            print(f"   📊 Tools run: {summary.get('tools_run_successfully', 0)}")
                    
        except Exception as e:
            print(f"   ❌ Failed to run analysis: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("Test completed!")
        print("=" * 60)

if __name__ == "__main__":
    test_analysis_integration()
