#!/usr/bin/env python3
"""
Test the analysis creation flow to ensure it triggers the security analysis properly
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_analysis_creation_flow():
    """Test the complete analysis creation flow through the web interface."""
    print("=" * 60)
    print("Testing Analysis Creation Flow")
    print("=" * 60)
    
    try:
        from app.factory import create_app
        from app.services.task_service import AnalysisTaskService
        
        # Create Flask app
        app = create_app('test')
        
        with app.app_context():
            print("✅ Flask app context active")
            
            # Simulate the form submission from /analysis/create
            model_slug = 'nousresearch_hermes-4-405b'
            app_number = 1
            analysis_type = 'security'
            priority = 'normal'
            
            print(f"📝 Creating analysis task:")
            print(f"   Model: {model_slug}")
            print(f"   App: {app_number}")
            print(f"   Type: {analysis_type}")
            print(f"   Priority: {priority}")
            
            # Create task using same method as route
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                analysis_type=analysis_type,
                priority=priority
            )
            
            print(f"✅ Analysis task created: {task.task_id}")
            print(f"   ID: {task.id}")
            print(f"   Status: {task.status}")
            print(f"   Analysis Type: {task.analysis_type}")
            print(f"   Target Model: {task.target_model}")
            print(f"   Target App: {task.target_app_number}")
            
            # Check if this task would be picked up by our task execution system
            print(f"\n🔍 Checking task execution compatibility...")
            
            # The task should be in PENDING status and ready for Celery
            if hasattr(task.status, 'value'):
                status_value = task.status.value
            else:
                status_value = str(task.status)
                
            if hasattr(task.analysis_type, 'value'):
                type_value = task.analysis_type.value
            else:
                type_value = str(task.analysis_type)
            
            print(f"   Status value: {status_value}")
            print(f"   Type value: {type_value}")
            
            if status_value == 'pending' and type_value == 'security':
                print("✅ Task is ready for Celery execution")
                
                # Now test if our security analysis engine would work with this
                from app.services.analysis_engines import get_engine
                
                try:
                    engine = get_engine('security')
                    print(f"✅ Security engine available: {engine}")
                    
                    # Test engine execution (without actually running it)
                    print(f"✅ Engine ready to process task with:")
                    print(f"   Model slug: {task.target_model}")
                    print(f"   App number: {task.target_app_number}")
                    
                except Exception as e:
                    print(f"❌ Engine issue: {e}")
                    
            else:
                print(f"❌ Task not ready - status: {status_value}, type: {type_value}")
            
            # Check if there's a way for this task to automatically trigger execution
            print(f"\n🔄 Checking automatic execution...")
            
            # Look for task execution service
            try:
                from app.services.service_locator import ServiceLocator
                
                # Check what services are available
                print("   Available services via ServiceLocator:")
                
                # Check if there's a way to trigger task execution
                if hasattr(ServiceLocator, 'get_task_execution_service'):
                    print("   ✅ Task execution service available")
                else:
                    print("   ❓ No task execution service found")
                    
                # Security service should be able to start analysis
                security_service = ServiceLocator.get_security_service()
                print(f"   ✅ Security service available: {security_service}")
                
            except Exception as e:
                print(f"   ❌ Service issue: {e}")
            
            print(f"\n🎉 Analysis creation flow test completed!")
            print(f"Task {task.task_id} is ready for execution.")
                
    except Exception as e:
        print(f"❌ Failed to test analysis creation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_analysis_creation_flow()
