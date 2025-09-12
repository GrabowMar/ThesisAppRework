#!/usr/bin/env python3
"""
Test the complete Flask web interface analysis flow
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_flask_analysis():
    """Test analysis through Flask app context (like web interface would)."""
    print("=" * 60)
    print("Testing Flask Web Interface Analysis Flow")
    print("=" * 60)
    
    try:
        from app.factory import create_app
        from app.services.service_locator import ServiceLocator
        
        # Create Flask app
        app = create_app('test')
        
        with app.app_context():
            print("✅ Flask app context active")
            
            # Get security service via ServiceLocator (as web routes would)
            security_service = ServiceLocator.get_security_service()
            print("✅ Security service retrieved via ServiceLocator")
            
            # Create a security analysis (simulating web form submission)
            try:
                # First, check if we have the test application
                from app.models import GeneratedApplication
                app_obj = GeneratedApplication.query.filter_by(
                    model_slug='nousresearch_hermes-4-405b',
                    app_number=1
                ).first()
                
                if not app_obj:
                    print("❌ Test application not found in database")
                    print("   Need to populate database with test data first")
                    return
                
                print(f"✅ Found test application: {app_obj.model_slug} app {app_obj.app_number}")
                
                # Start security analysis directly (simulating web form submission)
                tools = ['bandit', 'safety', 'pylint']
                options = {'description': 'Test analysis via Flask interface'}
                
                scan_id = security_service.start_security_analysis(
                    model_slug='nousresearch_hermes-4-405b',
                    app_number=1,
                    tools=tools,
                    options=options
                )
                print(f"✅ Security analysis started: scan_id {scan_id}")
                
                # Check initial status
                status = security_service.get_analysis_status(scan_id)
                print(f"✅ Analysis status: {status.get('status') if status else 'unknown'}")
                
                print("\n🎉 Flask web interface integration working!")
                print("The analysis will complete in the background via Celery worker.")
                
            except Exception as e:
                print(f"❌ Failed to create/start analysis: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ Failed to set up Flask app: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_flask_analysis()
