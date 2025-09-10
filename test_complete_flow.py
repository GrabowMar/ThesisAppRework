#!/usr/bin/env python3
"""
Test the complete frontend-to-backend analysis flow
"""
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_complete_analysis_flow():
    """Test the complete analysis flow from creation to execution."""
    print("=" * 60)
    print("Testing Complete Analysis Flow")
    print("=" * 60)
    
    try:
        from app.factory import create_app
        from app.services.task_service import AnalysisTaskService
        
        # Create Flask app (this will initialize the task execution service)
        app = create_app('test')
        
        with app.app_context():
            print("✅ Flask app context active")
            print("✅ Task execution service should be initialized")
            
            # Import the task execution service after app initialization
            from app.services.task_execution_service import task_execution_service
            
            # Create an analysis task (like the frontend would)
            model_slug = 'nousresearch_hermes-4-405b'
            app_number = 1
            analysis_type = 'security'
            
            print(f"\n📝 Creating analysis task:")
            print(f"   Model: {model_slug}")
            print(f"   App: {app_number}")
            print(f"   Type: {analysis_type}")
            
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type=analysis_type,
                priority='normal'
            )
            
            print(f"✅ Task created: {task.task_id}")
            print(f"   Status: {task.status}")
            
            # Now check if the task execution service can pick it up
            if task_execution_service:
                print(f"\n🔄 Task execution service is available")
                
                # Manually trigger task processing (simulating what the background thread does)
                print("   Triggering task processing...")
                processed_count = task_execution_service.process_once(limit=1)
                
                print(f"   Processed {processed_count} tasks")
                
                if processed_count > 0:
                    # Refresh the task from database to see updated status
                    from app.extensions import db
                    db.session.refresh(task)
                    
                    print(f"✅ Task execution completed!")
                    print(f"   Final Status: {task.status}")
                    print(f"   Progress: {task.progress_percentage}%")
                    print(f"   Duration: {task.actual_duration}s" if task.actual_duration else "   Duration: unknown")
                    
                    # Check if results were stored
                    if hasattr(task, 'get_metadata'):
                        try:
                            metadata = task.get_metadata()
                            if metadata:
                                print(f"   ✅ Analysis results stored in metadata")
                                if 'analysis' in metadata:
                                    analysis_data = metadata['analysis']
                                    if 'summary' in analysis_data:
                                        summary = analysis_data['summary']
                                        print(f"   📊 Total issues found: {summary.get('total_issues_found', 0)}")
                            else:
                                print(f"   ❓ No metadata stored")
                        except Exception as e:
                            print(f"   ❌ Failed to read metadata: {e}")
                    
                    # Check final status
                    status_value = task.status.value if hasattr(task.status, 'value') else str(task.status)
                    if status_value == 'completed':
                        print(f"\n🎉 COMPLETE SUCCESS! Analysis flow working end-to-end:")
                        print(f"   Frontend → Task Creation → Task Execution → Analysis Engine → Results")
                    elif status_value == 'failed':
                        print(f"\n⚠️  Task completed but with failed status - check logs for analysis errors")
                    else:
                        print(f"\n❓ Unexpected final status: {status_value}")
                        
                else:
                    print(f"   ❌ No tasks were processed")
                    
            else:
                print(f"❌ Task execution service not available")
                
    except Exception as e:
        print(f"❌ Failed to test complete flow: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_analysis_flow()
